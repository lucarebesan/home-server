"""Normalize imported Nextcloud names to NFC without changing the raw archive."""

from pathlib import Path
import json
import os
import sys
import unicodedata


root = Path("/nextcloud/data/luca/files/Box.com")
state = Path("/state")
apply = sys.argv[1:] == ["--apply"]
if not root.is_dir():
    raise SystemExit("Box.com destination missing")

changes = []
collisions = []
for parent, directories, files in os.walk(root, topdown=False):
    entries = files + directories
    normalized = {}
    for name in entries:
        new_name = unicodedata.normalize("NFC", name)
        normalized.setdefault(new_name, []).append(name)
    for new_name, names in normalized.items():
        if len(names) > 1:
            collisions.append({"parent": str(Path(parent).relative_to(root)), "names": names})
    for name in entries:
        new_name = unicodedata.normalize("NFC", name)
        if new_name == name:
            continue
        old = Path(parent) / name
        new = Path(parent) / new_name
        if new.exists():
            collisions.append({"old": str(old.relative_to(root)), "new": str(new.relative_to(root))})
        changes.append({"old": str(old.relative_to(root)), "new": str(new.relative_to(root)), "directory": old.is_dir()})

if collisions:
    print(json.dumps({"changes": len(changes), "collisions": len(collisions)}), flush=True)
    raise SystemExit("NFC name collisions; no changes made")

if apply:
    # os.walk listed children before parents, so directory renames remain valid.
    for item in changes:
        (root / item["old"]).rename(root / item["new"])
    output = state / "box-nextcloud-nfc-renames.json"
    output.write_text(json.dumps(changes, indent=2, ensure_ascii=False), encoding="utf-8")
    output.chmod(0o600)
    os.chown(output, os.stat("/source").st_uid, os.stat("/source").st_gid)

print(json.dumps({"applied": apply, "files": sum(not item["directory"] for item in changes), "directories": sum(item["directory"] for item in changes), "collisions": len(collisions)}), flush=True)
