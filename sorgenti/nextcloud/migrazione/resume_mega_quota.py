"""Resume a free MEGA download after transfer quota windows reset."""

from pathlib import Path
from urllib.request import Request, urlopen
import json
import os
import subprocess
import time


os.umask(0o077)
home = Path.home()
state = home / ".local" / "state"
rclone = str(home / ".local" / "bin" / "rclone")
destination = str(home / "mega-import")
status = state / "mega-verified.status"
log = state / "mega-quota-resume.log"
six_hours = 6 * 3600


def notify(message):
    try:
        token = (home / ".config" / "ecm" / "ha_token").read_text(encoding="utf-8").strip()
        request = Request(
            "http://127.0.0.1:8123/api/services/notify/mobile_app_iphone_luca",
            data=json.dumps({"title": "Migrazione MEGA", "message": message}).encode("utf-8"),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15):
            pass
    except Exception:
        pass


def record(message):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    with log.open("a", encoding="utf-8") as handle:
        handle.write(stamp + " " + message + "\n")
    print(stamp + " " + message, flush=True)


def run(args, logfile):
    result = subprocess.run([rclone, *args, "--log-file", str(logfile), "--log-level", "INFO", "--stats", "5m"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode


record("Quota limit reached; waiting 6 hours before retry")
time.sleep(six_hours)
for round_number in range(1, 11):
    record(f"Copy attempt {round_number}")
    copy_log = state / "mega-quota-copy.log"
    before = copy_log.stat().st_size if copy_log.exists() else 0
    copy_exit = run(
        ["copy", "mega:", destination, "--size-only", "--create-empty-src-dirs", "--transfers", "2", "--checkers", "4", "--retries", "1", "--low-level-retries", "1", "--mega-use-https"],
        copy_log,
    )
    record(f"Copy exit {copy_exit}")
    if copy_exit == 0:
        time.sleep(5)
        check_exit = run(["check", "mega:", destination, "--size-only", "--one-way", "--checkers", "4", "--mega-use-https"], state / "mega-check.log")
        record(f"Check exit {check_exit}")
        if check_exit == 0:
            status.write_text("verified\n", encoding="ascii")
            status.chmod(0o600)
            record("MEGA verified")
            raise SystemExit(0)
        time.sleep(60)
        continue
    with copy_log.open("rb") as handle:
        handle.seek(before)
        new_log = handle.read().decode("utf-8", errors="replace")
    if "Bandwidth Limit Exceeded" in new_log or "Http Status: 509" in new_log:
        record("Transfer quota still exhausted; waiting 6 hours")
        time.sleep(six_hours)
    else:
        record("Unexpected copy error; waiting 30 minutes")
        time.sleep(30 * 60)

status.write_text("failed\n", encoding="ascii")
status.chmod(0o600)
notify("Il download MEGA richiede un controllo dopo più tentativi. Apri la chat Codex.")
record("MEGA failed after 10 attempts")
raise SystemExit(1)
