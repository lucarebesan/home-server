"""Import verified Box files into the Nextcloud data volume.

Run only after the complete rclone copy/check and final ransomware analysis.
The source trees are mounted read-only; the destination is a dedicated folder.
"""

from hashlib import sha1
from pathlib import Path
import json
import os
import shutil
import sys


name = sys.argv[1] if len(sys.argv) > 1 else "box"
if name not in ("box", "mega"):
    raise SystemExit("Expected box or mega")
source = Path("/source")
recovered = Path("/recovered")
state = Path("/state")
destination = Path("/nextcloud/data/luca/files") / ("Box.com" if name == "box" else "MEGA")
analysis = json.loads((state / (name + "-import-analysis.json")).read_text(encoding="utf-8"))
recovery = json.loads((state / "box-recovery-report.json").read_text(encoding="utf-8")) if name == "box" else {"results": []}
excluded = {item["path"] for item in analysis["encrypted"]} | set(analysis["notes"])
extensions = tuple("." + extension.lower() for extension in analysis["extensions"])
expected = analysis["file_count"] - len(excluded)
if expected < 0:
    raise RuntimeError("Invalid file count in analysis")
if not source.is_dir() or (name == "box" and not recovered.is_dir()) or not destination.parent.is_dir():
    raise RuntimeError("Missing import mount")


def digest(path):
    result = sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def make_parent(path):
    pending = []
    current = path.parent
    while not current.exists():
        pending.append(current)
        current = current.parent
    for directory in reversed(pending):
        directory.mkdir(mode=0o750)
        os.chown(directory, 33, 33)


copied = 0
already_present = 0
collisions = []
counted_source = 0
for path in source.rglob("*"):
    if not path.is_file():
        continue
    counted_source += 1
    relative = path.relative_to(source).as_posix()
    if relative in excluded or relative.lower().endswith(extensions):
        continue
    target = destination / relative
    make_parent(target)
    if target.exists():
        if target.is_file() and target.stat().st_size == path.stat().st_size and digest(target) == digest(path):
            already_present += 1
            continue
        collisions.append(relative)
        continue
    temporary = target.with_name(target.name + ".partial-box-import")
    with path.open("rb") as input_file, temporary.open("wb") as output_file:
        shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
        output_file.flush()
        os.fsync(output_file.fileno())
    shutil.copystat(path, temporary)
    os.chown(temporary, 33, 33)
    os.replace(temporary, target)
    if target.stat().st_size != path.stat().st_size:
        raise RuntimeError("Copied file size mismatch: " + relative)
    copied += 1
    if copied % 500 == 0:
        print(f"Imported {copied} clean Box files", flush=True)

if counted_source != analysis["file_count"]:
    raise RuntimeError("Source changed after analysis")

directory_count = 0
for path in source.rglob("*"):
    if path.is_dir():
        make_parent(destination / path.relative_to(source) / ".directory-marker")
        directory_count += 1

recovered_copied = 0
recovered_already_present = 0
recovered_skipped = []
for item in recovery["results"]:
    if not item["sha1_verified"] or item["format"] != "expected_format":
        recovered_skipped.append(item["recovered"])
        continue
    relative = item["recovered"]
    original = recovered / relative
    target = destination / relative
    if not original.is_file():
        raise RuntimeError("Verified recovery missing from disk: " + relative)
    make_parent(target)
    if target.exists():
        if target.is_file() and target.stat().st_size == original.stat().st_size and digest(target) == digest(original):
            recovered_already_present += 1
            continue
        collisions.append(relative)
        continue
    temporary = target.with_name(target.name + ".partial-box-import")
    with original.open("rb") as input_file, temporary.open("wb") as output_file:
        shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
        output_file.flush()
        os.fsync(output_file.fileno())
    shutil.copystat(original, temporary)
    os.chown(temporary, 33, 33)
    os.replace(temporary, target)
    if target.stat().st_size != original.stat().st_size:
        raise RuntimeError("Recovered file size mismatch: " + relative)
    recovered_copied += 1

report = {
    "raw_file_count": counted_source,
    "raw_directory_count": directory_count,
    "excluded_encrypted_and_notes": len(excluded),
    "expected_clean_files": expected,
    "copied_clean_files": copied,
    "already_present_clean_files": already_present,
    "copied_recovered_files": recovered_copied,
    "already_present_recovered_files": recovered_already_present,
    "unverified_recovered_files_not_imported": recovered_skipped,
    "collisions": collisions,
}
output = state / ("nextcloud-" + name + "-import-report.json")
output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
output.chmod(0o600)
os.chown(output, source.stat().st_uid, source.stat().st_gid)
print(json.dumps({key: value for key, value in report.items() if key not in ("collisions", "unverified_recovered_files_not_imported")}, ensure_ascii=False), flush=True)
if copied + already_present != expected or collisions:
    raise RuntimeError("Import count mismatch or file collisions")
