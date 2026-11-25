from collections import defaultdict
from configparser import ConfigParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json
import subprocess
import time


home = Path.home()
state = home / ".local" / "state"
rclone = str(home / ".local" / "bin" / "rclone")
report = json.loads((state / "box-import-analysis.json").read_text(encoding="utf-8"))
groups = defaultdict(list)
for candidate in report["encrypted"]:
    relative = Path(candidate["path"])
    groups[relative.parent.as_posix()].append(candidate)


def current_token():
    config = ConfigParser(interpolation=None)
    config.read(home / ".config" / "rclone" / "rclone.conf")
    return json.loads(config["box"]["token"])["access_token"]


def api_json(url):
    for attempt in range(6):
        request = Request(
            url,
            headers={
                "Authorization": "Bearer " + current_token(),
                "User-Agent": "Box-recovery-audit/1.0",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in (401, 429, 500, 502, 503, 504) or attempt == 5:
                raise
            if error.code == 401:
                subprocess.run([rclone, "lsd", "box:"], check=True, capture_output=True)
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError("API retries exhausted")


results = []
errors = []
for parent, candidates in groups.items():
    try:
        listing = subprocess.run(
            [rclone, "lsjson", "--files-only", "box:" + parent],
            check=True,
            capture_output=True,
            text=True,
        )
        by_name = {item.get("Name"): item for item in json.loads(listing.stdout)}
    except Exception as error:
        errors.append({"parent": parent, "error": type(error).__name__})
        continue
    for candidate in candidates:
        item = by_name.get(Path(candidate["path"]).name)
        if not item or not item.get("ID"):
            errors.append({"path": candidate["path"], "error": "file_id_missing"})
            continue
        file_id = item["ID"]
        try:
            versions = api_json(f"https://api.box.com/2.0/files/{file_id}/versions?limit=100")
            entries = versions.get("entries", [])
            results.append(
                {
                    "path": candidate["path"],
                    "expected_original": candidate["expected_original"],
                    "file_id": file_id,
                    "current_size": item.get("Size"),
                    "previous_versions": [
                        {key: version.get(key) for key in ("id", "created_at", "modified_at", "size", "sha1")}
                        for version in entries
                    ],
                }
            )
        except Exception as error:
            errors.append({"path": candidate["path"], "error": type(error).__name__})
    print(f"Audited {len(results)}/{len(report['encrypted'])} encrypted files", flush=True)

output = state / "box-versions-audit.json"
output.write_text(json.dumps({"results": results, "errors": errors}, indent=2, ensure_ascii=False), encoding="utf-8")
output.chmod(0o600)
print(
    json.dumps(
        {
            "encrypted_files": len(report["encrypted"]),
            "audited": len(results),
            "with_previous_versions": sum(bool(item["previous_versions"]) for item in results),
            "without_previous_versions": sum(not item["previous_versions"] for item in results),
            "errors": len(errors),
            "previous_version_bytes": sum(
                version.get("size") or 0
                for item in results
                for version in item["previous_versions"]
            ),
        },
        ensure_ascii=False,
    ),
    flush=True,
)
