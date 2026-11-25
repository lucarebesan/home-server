from collections import Counter
from pathlib import Path
import json
import re
import sys


name = sys.argv[1] if len(sys.argv) > 1 else "box"
if name not in ("box", "mega"):
    raise SystemExit("Expected box or mega")
root = Path.home() / (name + "-import")
state = Path.home() / ".local" / "state"
note_pattern = re.compile(r"^README-RECOVER-([A-Za-z0-9]+)\.txt$", re.I)
field_pattern = re.compile(r"^Extension:\s*([A-Za-z0-9]+)\s*$", re.I | re.M)
notes = []
extensions = set()

for path in root.rglob("*"):
    if not path.is_file():
        continue
    match = note_pattern.match(path.name)
    if not match:
        continue
    notes.append(path.relative_to(root).as_posix())
    extensions.add(match.group(1))
    content = path.read_text(encoding="utf-8", errors="replace")
    extensions.update(field_pattern.findall(content))

encrypted = []
matched = Counter()
originals_present = 0
file_count = 0
byte_count = 0
for path in root.rglob("*"):
    if not path.is_file():
        continue
    file_count += 1
    byte_count += path.stat().st_size
    for extension in extensions:
        suffix = "." + extension
        if not path.name.lower().endswith(suffix.lower()):
            continue
        original = path.with_name(path.name[: -len(suffix)])
        present = original.is_file()
        originals_present += int(present)
        matched[extension] += 1
        encrypted.append(
            {
                "path": path.relative_to(root).as_posix(),
                "expected_original": original.relative_to(root).as_posix(),
                "original_present": present,
                "size": path.stat().st_size,
            }
        )
        break

report = {
    "file_count": file_count,
    "byte_count": byte_count,
    "ransom_note_count": len(notes),
    "extensions": sorted(extensions),
    "encrypted_count": len(encrypted),
    "encrypted_by_extension": dict(matched),
    "originals_present": originals_present,
    "notes": notes,
    "encrypted": encrypted,
}
output = state / (name + "-import-analysis.json")
output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
output.chmod(0o600)
print(
    json.dumps(
        {key: report[key] for key in (
            "file_count",
            "byte_count",
            "ransom_note_count",
            "extensions",
            "encrypted_count",
            "encrypted_by_extension",
            "originals_present",
        )},
        ensure_ascii=False,
    )
)
