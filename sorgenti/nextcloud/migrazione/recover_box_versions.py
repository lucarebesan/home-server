"""Download prior Box versions into a separate, private recovery tree.

Only files listed by the local encrypted-file audit are considered.  Current
Box files and the raw import are never modified.
"""

from configparser import ConfigParser
from hashlib import sha1
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile, is_zipfile
import json
import os
import subprocess
import time


home = Path.home()
state = home / ".local" / "state"
raw = home / "box-import"
recovered = home / "box-recovered"
audit = json.loads((state / "box-versions-audit.json").read_text(encoding="utf-8"))
recovered.mkdir(mode=0o700, exist_ok=True)
recovered.chmod(0o700)


def token():
    config = ConfigParser(interpolation=None)
    config.read(home / ".config" / "rclone" / "rclone.conf")
    return json.loads(config["box"]["token"])["access_token"]


def open_box(url):
    for attempt in range(6):
        request = Request(
            url,
            headers={"Authorization": "Bearer " + token(), "User-Agent": "Box-recovery/1.0"},
        )
        try:
            return urlopen(request, timeout=90)
        except HTTPError as error:
            if error.code == 401 and attempt < 5:
                subprocess.run(
                    [str(home / ".local" / "bin" / "rclone"), "lsd", "box:"],
                    check=True,
                    capture_output=True,
                )
            elif error.code not in (429, 500, 502, 503, 504) or attempt == 5:
                raise
            time.sleep(min(30, 2**attempt))
    raise RuntimeError("Box retries exhausted")


def file_kind(path, suffix=None):
    suffix = suffix or path.suffix.lower()
    with path.open("rb") as source:
        head = source.read(16)
    if is_zipfile(path):
        try:
            with ZipFile(path) as archive:
                if archive.testzip() is not None:
                    return "invalid_zip"
                names = set(archive.namelist())
                if suffix in (".odt", ".ods", ".odp"):
                    expected = {
                        ".odt": "application/vnd.oasis.opendocument.text",
                        ".ods": "application/vnd.oasis.opendocument.spreadsheet",
                        ".odp": "application/vnd.oasis.opendocument.presentation",
                    }[suffix]
                    return "expected_format" if "mimetype" in names and archive.read("mimetype").decode("ascii", errors="replace") == expected else "unknown_format"
                if suffix in (".docx", ".xlsx", ".pptx"):
                    prefix = {".docx": "word/", ".xlsx": "xl/", ".pptx": "ppt/"}[suffix]
                    return "expected_format" if "[Content_Types].xml" in names and any(name.startswith(prefix) for name in names) else "unknown_format"
                return "expected_format" if suffix in (".zip", ".jar") else "valid_zip"
        except (BadZipFile, OSError):
            return "invalid_zip"
    signatures = {
        ".pdf": b"%PDF-",
        ".png": b"\x89PNG\r\n\x1a\n",
        ".jpg": b"\xff\xd8\xff",
        ".jpeg": b"\xff\xd8\xff",
        ".gif": b"GIF8",
        ".sqlite": b"SQLite format 3\x00",
    }
    if suffix in signatures:
        return "expected_format" if head.startswith(signatures[suffix]) else "unknown_format"
    if suffix in (".doc", ".xls", ".ppt"):
        return "expected_format" if head.startswith(bytes.fromhex("D0CF11E0A1B11AE1")) else "unknown_format"
    if suffix in (".txt", ".csv", ".xml", ".html", ".json"):
        return "text_or_unknown"
    return "unknown_format"


results = []
errors = []
for item in audit["results"]:
    versions = item["previous_versions"]
    if not versions:
        continue
    relative = Path(item["expected_original"])
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        errors.append({"path": item["path"], "error": "unsafe_path"})
        continue
    destination = recovered / relative
    if (raw / relative).is_file():
        errors.append({"path": item["path"], "error": "original_already_present"})
        continue
    recognized = {".odt", ".ods", ".odp", ".docx", ".xlsx", ".pptx", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".sqlite", ".doc", ".xls", ".ppt", ".zip", ".jar"}
    # Box lists older versions newest first.  Try them in that order.
    for version in versions:
        version_id = version.get("id")
        expected_sha1 = version.get("sha1")
        expected_size = version.get("size")
        if not version_id or not expected_sha1 or expected_size is None:
            continue
        if destination.exists():
            digest = sha1()
            with destination.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            if destination.stat().st_size == expected_size and digest.hexdigest().lower() == expected_sha1.lower():
                results.append({"path": item["path"], "recovered": relative.as_posix(), "version_id": version_id, "size": expected_size, "sha1_verified": True, "format": file_kind(destination), "existing": True})
                break
            continue
        destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        temporary = destination.with_name(destination.name + ".partial-box-recovery")
        try:
            url = f"https://api.box.com/2.0/files/{item['file_id']}/content?" + urlencode({"version": version_id})
            digest = sha1()
            size = 0
            with open_box(url) as response, temporary.open("wb") as output:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    size += len(chunk)
                    digest.update(chunk)
                    output.write(chunk)
            if size != expected_size or digest.hexdigest().lower() != expected_sha1.lower():
                raise RuntimeError("Box metadata mismatch")
            format_status = file_kind(temporary, relative.suffix.lower())
            if relative.suffix.lower() in recognized and format_status != "expected_format":
                raise RuntimeError("Previous version has unexpected file format")
            temporary.chmod(0o600)
            os.replace(temporary, destination)
            results.append({"path": item["path"], "recovered": relative.as_posix(), "version_id": version_id, "size": size, "sha1_verified": True, "format": format_status, "existing": False})
            break
        except Exception as error:
            temporary.unlink(missing_ok=True)
            errors.append({"path": item["path"], "version_id": version_id, "error": type(error).__name__})
    if destination.exists() and not any(result["path"] == item["path"] for result in results):
        errors.append({"path": item["path"], "error": "existing_recovered_file_unmatched"})
    print(f"Recovered {len(results)} of {len(audit['results'])} audited files", flush=True)

output = state / "box-recovery-report.json"
output.write_text(json.dumps({"results": results, "errors": errors}, indent=2, ensure_ascii=False), encoding="utf-8")
output.chmod(0o600)
print(json.dumps({"recovered": len(results), "format_counts": {kind: sum(item["format"] == kind for item in results) for kind in sorted({item["format"] for item in results})}, "errors": len(errors)}, ensure_ascii=False))
