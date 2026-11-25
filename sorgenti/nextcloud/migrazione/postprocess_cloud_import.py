"""Finish a verified Box or MEGA migration into separate Nextcloud folders."""

from pathlib import Path
from urllib.request import Request, urlopen
import json
import os
import re
import subprocess
import sys
import time


os.umask(0o077)
home = Path.home()
state = home / ".local" / "state"
name = sys.argv[1]
if name not in ("box", "mega"):
    raise SystemExit("Expected box or mega")
log_path = state / (name + "-postprocess.log")
status_path = state / (name + "-nextcloud.status")
verified_path = state / (name + "-verified.status")


def set_status(value):
    status_path.write_text(value + "\n", encoding="ascii")
    status_path.chmod(0o600)


def notify(message):
    try:
        token = (home / ".config" / "ecm" / "ha_token").read_text(encoding="utf-8").strip()
        request = Request(
            "http://127.0.0.1:8123/api/services/notify/mobile_app_iphone_luca",
            data=json.dumps({"title": "Migrazione cloud", "message": message}).encode("utf-8"),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15):
            pass
    except Exception:
        pass


def run(label, command):
    print(label, flush=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write("\n--- " + label + " ---\n")
        log.flush()
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        log.write("exit=" + str(result.returncode) + "\n")
    if result.returncode != 0:
        raise RuntimeError(label + " failed; inspect " + str(log_path))


def scan_nextcloud(folder):
    label = "Scan Nextcloud file index"
    command = ["docker", "exec", "-u", "www-data", "nextcloud-app", "php", "occ", "files:scan", "--path=luca/files/" + folder]
    print(label, flush=True)
    result = subprocess.run(command, capture_output=True, text=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write("\n--- " + label + " ---\n" + result.stdout + result.stderr + "\nexit=" + str(result.returncode) + "\n")
    if result.returncode != 0:
        raise RuntimeError("Nextcloud file scan failed")
    rows = re.findall(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|", result.stdout, re.M)
    if not rows:
        raise RuntimeError("Nextcloud scan summary not found")
    files = int(rows[-1][1])
    errors = int(rows[-1][5])
    if errors:
        raise RuntimeError("Nextcloud scan reported file errors")
    return files


try:
    while True:
        if verified_path.is_file():
            verification = verified_path.read_text(encoding="ascii").strip()
            if verification == "verified":
                break
            if verification == "failed":
                set_status("copy_verification_failed")
                raise SystemExit(1)
        time.sleep(30)

    print(name + " copy verified; beginning analysis", flush=True)
    run("Analyze raw archive", ["python3", str(state / "analyze_box_import.py"), name])
    if name == "box":
        run("Audit Box previous versions", ["python3", str(state / "audit_box_versions.py")])
        run("Recover Box previous versions", ["python3", str(state / "recover_box_versions.py")])
    else:
        time.sleep(5)
        run("Audit MEGA paths and duplicate names", ["python3", str(state / "audit_mega_paths.py")])

    command = [
        "docker", "run", "--rm", "--network", "none",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-v", str(home / (name + "-import")) + ":/source:ro",
        "-v", str(state) + ":/state",
        "-v", "nextcloud_html:/nextcloud",
        "-v", str(state / "import_box_to_nextcloud.py") + ":/app/import.py:ro",
    ]
    if name == "box":
        command += ["-v", str(home / "box-recovered") + ":/recovered:ro"]
    command += ["python:3.12-alpine", "python", "/app/import.py", name]
    run("Import into separate Nextcloud folder", command)
    folder = "Box.com" if name == "box" else "MEGA"
    scanned_files = scan_nextcloud(folder)

    analysis = json.loads((state / (name + "-import-analysis.json")).read_text(encoding="utf-8"))
    report = json.loads((state / ("nextcloud-" + name + "-import-report.json")).read_text(encoding="utf-8"))
    if report["collisions"] or report["copied_clean_files"] + report["already_present_clean_files"] != report["expected_clean_files"]:
        raise RuntimeError("Import report count mismatch")
    expected_files = report["expected_clean_files"] + report["copied_recovered_files"] + report["already_present_recovered_files"]
    if scanned_files != expected_files:
        raise RuntimeError("Nextcloud indexed file count differs from imported file count")
    needs_review = bool(analysis["encrypted_count"])
    if name == "box":
        audit = json.loads((state / "box-versions-audit.json").read_text(encoding="utf-8"))
        recovery = json.loads((state / "box-recovery-report.json").read_text(encoding="utf-8"))
        recovered = {item["path"] for item in recovery["results"] if item["sha1_verified"] and item["format"] == "expected_format"}
        encrypted = {item["path"] for item in analysis["encrypted"]}
        needs_review = bool(encrypted - recovered or audit["errors"])
    if needs_review:
        set_status("imported_with_review")
        notify(name.upper() + " è in Nextcloud, ma alcuni file cifrati o incerti richiedono un controllo. Apri la chat Codex.")
    else:
        set_status("imported")
    print(name + " imported; review=" + str(needs_review), flush=True)
except SystemExit:
    raise
except Exception as error:
    set_status("failed")
    with log_path.open("a", encoding="utf-8") as log:
        log.write("\nPOSTPROCESS FAILED: " + type(error).__name__ + " " + str(error) + "\n")
    notify("L'importazione " + name.upper() + " in Nextcloud richiede un controllo. Apri la chat Codex.")
    print(type(error).__name__ + ": " + str(error), flush=True)
    raise SystemExit(1)
