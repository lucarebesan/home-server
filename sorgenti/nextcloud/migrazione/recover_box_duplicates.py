"""Preserve Box objects that share a path but have different content."""

from configparser import ConfigParser
from hashlib import sha1
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json
import os
import subprocess
import time


home = Path.home()
state = home / ".local/state"
source = json.loads((state / "box-duplicate-audit.json").read_text(encoding="utf-8"))
destination_root = home / "box-duplicates"
destination_root.mkdir(mode=0o700, exist_ok=True)


def token():
    config = ConfigParser(interpolation=None)
    config.read(home / ".config/rclone/rclone.conf")
    return json.loads(config["box"]["token"])["access_token"]


def download(file_id, target, expected_size, expected_sha1):
    for attempt in range(6):
        temporary = target.with_name(target.name + ".partial-box-download")
        digest = sha1()
        size = 0
        try:
            request = Request(
                f"https://api.box.com/2.0/files/{file_id}/content",
                headers={"Authorization": "Bearer " + token(), "User-Agent": "Box-duplicate-preservation/1.0"},
            )
            with urlopen(request, timeout=90) as response, temporary.open("wb") as output:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                output.flush()
                os.fsync(output.fileno())
            if size != expected_size or digest.hexdigest().lower() != expected_sha1.lower():
                raise RuntimeError("Box duplicate checksum mismatch")
            temporary.chmod(0o600)
            os.replace(temporary, target)
            return
        except HTTPError as error:
            temporary.unlink(missing_ok=True)
            if error.code == 401 and attempt < 5:
                subprocess.run([str(home / ".local/bin/rclone"), "lsd", "box:"], check=True, capture_output=True)
            elif error.code not in (429, 500, 502, 503, 504) or attempt == 5:
                raise
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        time.sleep(min(30, 2**attempt))
    raise RuntimeError("Box duplicate download retries exhausted")


results = []
for item in source:
    relative = Path(item["path"])
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise RuntimeError("Unsafe duplicate path")
    if not item["local_sha1"]:
        raise RuntimeError("Original path missing from raw archive")
    if sum(entry.get("sha1", "").lower() == item["local_sha1"].lower() for entry in item["entries"]) != 1:
        raise RuntimeError("Expected exactly one matching local object")
    for entry in item["entries"]:
        if entry.get("sha1", "").lower() == item["local_sha1"].lower():
            continue
        file_id = entry["id"]
        if not file_id.isdigit():
            raise RuntimeError("Unsafe Box file ID")
        name = relative.stem + " (Box duplicate " + file_id + ")" + relative.suffix
        target_relative = relative.with_name(name)
        target = destination_root / target_relative
        target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if target.exists():
            digest = sha1(target.read_bytes()).hexdigest()
            if target.stat().st_size != entry["size"] or digest.lower() != entry["sha1"].lower():
                raise RuntimeError("Existing duplicate copy differs from Box")
        else:
            download(file_id, target, entry["size"], entry["sha1"])
        with target.open("rb") as handle:
            head = handle.read(4)
        format_status = "expected_format" if target.suffix.lower() in (".jpg", ".jpeg") and head.startswith(b"\xff\xd8\xff") else "unknown_format"
        results.append({"original_path": item["path"], "saved_path": target_relative.as_posix(),
                        "file_id": file_id, "size": entry["size"], "sha1": entry["sha1"], "format": format_status})

output = state / "box-duplicates-recovery.json"
output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
output.chmod(0o600)
print(json.dumps({"preserved_distinct_objects": len(results), "verified_bytes": sum(x["size"] for x in results),
                  "recognized_format": sum(x["format"] == "expected_format" for x in results)}), flush=True)
