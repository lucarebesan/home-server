"""Cross-check every active MEGA path and size against the raw local copy."""

from collections import Counter
from pathlib import Path
import json
import subprocess


home = Path.home()
state = home / ".local" / "state"
root = home / "mega-import"
rclone = str(home / ".local" / "bin" / "rclone")
listing = subprocess.run(
    [rclone, "lsjson", "--recursive", "--files-only", "mega:"],
    check=True,
    capture_output=True,
    text=True,
    timeout=7200,
)
remote = json.loads(listing.stdout)
paths = Counter(item["Path"] for item in remote)
duplicates = [{"path": path, "count": count} for path, count in paths.items() if count > 1]
local = {path.relative_to(root).as_posix(): path.stat().st_size for path in root.rglob("*") if path.is_file()}
remote_unique = {item["Path"]: item.get("Size") for item in remote}
missing = sorted(set(remote_unique) - set(local))
extra = sorted(set(local) - set(remote_unique))
size_mismatch = sorted(path for path in set(remote_unique) & set(local) if remote_unique[path] != local[path])
report = {
    "remote_file_entries": len(remote),
    "remote_unique_paths": len(remote_unique),
    "local_files": len(local),
    "remote_bytes_including_duplicates": sum(item.get("Size") or 0 for item in remote),
    "local_bytes": sum(local.values()),
    "duplicate_paths": duplicates,
    "missing": missing,
    "extra": extra,
    "size_mismatch": size_mismatch,
}
output = state / "mega-path-audit.json"
output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
output.chmod(0o600)
print(json.dumps({key: (len(value) if isinstance(value, list) else value) for key, value in report.items()}, ensure_ascii=False), flush=True)
if duplicates or missing or size_mismatch:
    raise SystemExit("MEGA path audit found files needing attention")
