"""Finish and verify an already running cloud download if SSH disconnects."""

from pathlib import Path
from urllib.request import Request, urlopen
import json
import os
import subprocess
import sys
import time


home = Path.home()
state = home / ".local" / "state"
rclone = str(home / ".local" / "bin" / "rclone")
name = sys.argv[1]
initial_pid = int(sys.argv[2])
if name not in ("box", "mega"):
    raise SystemExit("Expected box or mega")
remote = name + ":"
destination = home / (name + "-import")
status = state / (name + "-verified.status")
copy_flags = ["--create-empty-src-dirs", "--transfers", "4", "--checkers", "4", "--retries", "10"]
check_flags = ["--one-way", "--checkers", "4"]
if name == "box":
    copy_flags.append("--checksum")
    check_flags.append("--checksum")
else:
    copy_flags += ["--size-only", "--mega-use-https"]
    check_flags += ["--size-only", "--mega-use-https"]


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def notify_failure():
    try:
        token = (home / ".config" / "ecm" / "ha_token").read_text(encoding="utf-8").strip()
        body = json.dumps({"title": "Migrazione cloud", "message": f"La verifica di {name.upper()} sul mini PC richiede un controllo. Apri la chat Codex."}).encode("utf-8")
        request = Request(
            "http://127.0.0.1:8123/api/services/notify/mobile_app_iphone_luca",
            data=body,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15):
            pass
    except Exception:
        pass


print(f"Waiting for initial {name} copy PID {initial_pid}", flush=True)
while alive(initial_pid):
    time.sleep(30)
print("Initial copy ended; checking all remote files", flush=True)
time.sleep(5)

for attempt in range(1, 4):
    print(f"Check attempt {attempt}", flush=True)
    check = subprocess.run(
        [rclone, "check", remote, str(destination), *check_flags, "--log-file", str(state / f"{name}-check.log"), "--log-level", "INFO", "--stats", "5m"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if check.returncode == 0:
        status.write_text("verified\n", encoding="ascii")
        status.chmod(0o600)
        print(f"{name} verified", flush=True)
        break
    if attempt == 3:
        status.write_text("failed\n", encoding="ascii")
        status.chmod(0o600)
        notify_failure()
        print(f"{name} verification failed after 3 attempts", flush=True)
        raise SystemExit(1)
    print("Check found differences; resuming copy", flush=True)
    copy = subprocess.run(
        [rclone, "copy", remote, str(destination), *copy_flags, "--log-file", str(state / f"{name}-resume.log"), "--log-level", "INFO", "--stats", "5m"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"Resume copy returned {copy.returncode}", flush=True)
    time.sleep(5)
