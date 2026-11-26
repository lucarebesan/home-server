"""Import a verified duplicate and stage uncertain prior versions separately."""

from hashlib import sha1
from pathlib import Path
import json
import os
import shutil
import sys
import unicodedata


apply = sys.argv[1:] == ["--apply"]
state = Path("/state")
duplicates = Path("/duplicates")
recovered = Path("/recovered")
files_root = Path("/nextcloud/data/luca/files")
box_root = files_root / "Box.com"
review_root = files_root / "Box.com - recuperi da verificare"
if not box_root.is_dir():
    raise RuntimeError("Box.com folder missing")


def digest(path):
    result = sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def nfc_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise RuntimeError("Unsafe import path")
    return root.joinpath(*(unicodedata.normalize("NFC", part) for part in path.parts))


audit = json.loads((state / "box-versions-audit.json").read_text(encoding="utf-8"))
recovery = json.loads((state / "box-recovery-report.json").read_text(encoding="utf-8"))
duplicate_report = json.loads((state / "box-duplicates-recovery.json").read_text(encoding="utf-8"))
version_sha1 = {
    (item["path"], version["id"]): version["sha1"]
    for item in audit["results"] for version in item["previous_versions"]
}

jobs = []
for item in recovery["results"]:
    if item["format"] == "expected_format":
        continue
    if not item["sha1_verified"]:
        continue
    expected = version_sha1.get((item["path"], item["version_id"]))
    if not expected:
        raise RuntimeError("Recovered prior version missing from Box audit")
    jobs.append((recovered / item["recovered"], nfc_path(review_root, item["recovered"]),
                 item["size"], expected, "review"))
for item in duplicate_report:
    jobs.append((duplicates / item["saved_path"], nfc_path(box_root, item["saved_path"]),
                 item["size"], item["sha1"], "duplicate"))

targets = [str(job[1]) for job in jobs]
if len(set(targets)) != len(targets):
    raise RuntimeError("Two Box extras map to the same Nextcloud path")

copied = 0
already_present = 0
for source, target, size, expected_sha1, kind in jobs:
    if not source.is_file() or source.stat().st_size != size or digest(source).lower() != expected_sha1.lower():
        raise RuntimeError("Source recovery differs from verified Box version")
    if target.exists():
        if not target.is_file() or target.stat().st_size != size or digest(target).lower() != expected_sha1.lower():
            raise RuntimeError("Nextcloud path collision")
        already_present += 1
        continue
    if not apply:
        continue
    pending = []
    parent = target.parent
    while not parent.exists():
        pending.append(parent)
        parent = parent.parent
    for directory in reversed(pending):
        directory.mkdir(mode=0o750)
        os.chown(directory, 33, 33)
    temporary = target.with_name(target.name + ".partial-box-extra")
    with source.open("rb") as input_file, temporary.open("wb") as output_file:
        shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
        output_file.flush()
        os.fsync(output_file.fileno())
    shutil.copystat(source, temporary)
    os.chown(temporary, 33, 33)
    os.replace(temporary, target)
    copied += 1

report = {"apply": apply, "total_jobs": len(jobs), "review_files": sum(job[4] == "review" for job in jobs),
          "duplicate_files": sum(job[4] == "duplicate" for job in jobs),
          "copied": copied, "already_present": already_present}
if apply:
    output = state / "box-nextcloud-extras-report.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    output.chmod(0o600)
    os.chown(output, os.stat("/recovered").st_uid, os.stat("/recovered").st_gid)
print(json.dumps(report), flush=True)
