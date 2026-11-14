"""Campagna autorizzata delle sei coppie HEAT: cron locale, ripresa persistente."""
import argparse
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

import thermal_session as thermal


ROME = ZoneInfo("Europe/Rome")
PEAK_W, RESERVE_W = 2400, 300
STABLE_S, RETRY_S = 300, 900


def tag(folder):
    return "ECM_CONSUMPTION_" + hashlib.sha256(str(folder).encode()).hexdigest()[:12]


def save(folder, data):
    tmp = folder / "campaign.tmp"
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(folder / "campaign.json")


def cleanup(folder):
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode:
        return
    kept = [line for line in result.stdout.splitlines() if tag(folder) not in line]
    if kept != result.stdout.splitlines():
        subprocess.run(["crontab", "-"], input="\n".join(kept)+"\n", text=True, check=True)


def initialize(folder):
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "campaign.json").exists():
        raise RuntimeError("campagna già esistente; non azzerare i progressi")
    data = {"created": thermal.stamp(), "enabled": True, "status": "attesa",
            "plan": thermal.CONSUMPTION_PLAN, "minutes": 30, "minimum_minutes": 28,
            "completed": {}, "attempts": [], "active": None,
            "ready_since": None, "last_check": None, "retry_after": 0}
    save(folder, data)
    return data


def pending_codes(data):
    return [p[2] for p in data["plan"] if str(p[2]) not in data["completed"]]


def start_blocker(snap, now):
    if snap.get("season") != "INVERNO":
        return "attesa stagione INVERNO"
    if snap.get("manual") != "AUTO" or snap.get("acs_test") != "off" or snap.get("auto_tests") != "off":
        return "altro comando manuale o prova attiva"
    if snap.get("free_cooling") in ("ATTIVATO", "PREPARAZIONE", "unknown", "unavailable"):
        return "free cooling attivo o stato non valido"
    if any(snap.get(e) not in ("on", "off") for e in thermal.WRITERS):
        return "stato automazioni incompleto"
    if any(snap.get(e) != "on" for e in ("automation.nilan_write", "automation.10_ecm_inverno")):
        return "gestione climatica sospesa a mano"
    keys = ("soc", "pv", "load", "zg", "zn", "t11", "t12", "cp_w", "split_w", "ceiling")
    if any(thermal.num(snap.get(k)) is None for k in keys):
        return "dati numerici incompleti"
    # Le temperature template possono non essere ripubblicate finché il valore
    # resta uguale: per CP/Split verificare la sorgente batch, non l'età del valore.
    for key in ("soc", "pv", "load", "gateway"):
        ts = thermal.num(snap.get("reported_"+key))
        if ts is None or not -30 <= now-ts <= 180:
            return "dati non aggiornati: " + key
    if thermal.num(snap["soc"]) <= 40:
        return "batteria al 40% o inferiore"
    if thermal.num(snap["load"]) < 100:
        return "carico nullo o non plausibile"
    base = max(0, thermal.num(snap["load"])-thermal.num(snap["cp_w"])-thermal.num(snap["split_w"]))
    needed = max(thermal.num(snap["load"]), base+PEAK_W+RESERVE_W)
    if thermal.num(snap["pv"]) < needed:
        return f"FV insufficiente per il carico previsto ({needed:.0f} W)"
    ceiling = min(23.5, thermal.num(snap["ceiling"]))
    if max(thermal.num(snap["zg"]), thermal.num(snap["zn"])) >= ceiling-0.5:
        return "attesa margine termico di almeno 0,5 °C"
    if max(thermal.num(snap["t11"]), thermal.num(snap["t12"])) >= 60:
        return "bollitore al limite termico"
    if any(snap.get(k) != "RISCALDAMENTO" for k in ("cp_mode", "split_mode")):
        return "macchine non in HEAT"
    if snap.get("split_on") not in ("SPENTO", "ACCESO", "OFF", "ON") or snap.get("split_fan") not in ("BASSA", "MEDIA", "ALTA", "AUTOMATICA"):
        return "stato Toshiba non valido"
    if snap.get("cp_comp") != "OFF":
        since = thermal.num(snap.get("cp_changed"))
        if snap.get("cp_comp") != "ON" or since is None or now-since < 900:
            return "attesa minimo 15 minuti compressore CP"
    return None


def absorb_results(data, session):
    for payload in session.get("phase_results", {}).values():
        code = payload["code"]
        if code not in {p[2] for p in data["plan"]}:
            continue
        accepted = thermal.accepted_phase(30, payload["end"]-payload["start"],
                                          payload.get("original_result", payload["result"]),
                                          payload.get("coverage", {"good": 0}))
        if payload.get("accepted") and accepted:
            data["completed"][str(code)] = payload


def alive(folder):
    path = folder / "worker.json"
    if not path.exists():
        return False
    worker = json.loads(path.read_text())
    try:
        return (worker["boot"] == Path("/proc/sys/kernel/random/boot_id").read_text().strip()
                and str(folder).encode() in Path("/proc", str(worker["pid"]), "cmdline").read_bytes())
    except OSError:
        return False


def finish_attempt(folder, data, now):
    active = Path(data["active"])
    thermal.watch(active)
    path = active / "session.json"
    if not path.exists():
        if alive(active) or now-data["attempts"][-1]["started"] < 120:
            return False
        reason = "avvio non riuscito; nessuna automazione sospesa"
    else:
        session = json.loads(path.read_text())
        absorb_results(data, session)
        if not session.get("restored"):
            data["status"] = "in_corso" if alive(active) else "ripristino_da_verificare"
            return False
        reason = session.get("result") or "arresto del processo"
    data["attempts"][-1].update(finished=now, reason=reason)
    data["active"] = None
    data["ready_since"] = None
    if not pending_codes(data):
        data.update(status="completata", enabled=False, completed_at=thermal.stamp())
        save(folder, data)
        thermal.notify("Campagna consumi completata: acquisite tutte le sei combinazioni. Gestione ordinaria ripristinata.")
        cleanup(folder)
        return False
    recoverable = any(x in reason for x in ("FV insufficiente", "batteria", "limite termico", "limite bollitore", "temperature non disponibili", "condizioni iniziali", "avvio non riuscito", "dati elettrici")) or reason == "completata"
    if not recoverable:
        data.update(enabled=False, status="sospesa_da_verificare", reason=reason)
        thermal.notify("Campagna sospesa da verificare: " + reason + ". Gestione ordinaria ripristinata.")
        cleanup(folder)
    else:
        data.update(status="attesa", retry_after=now+RETRY_S, reason=reason)
        thermal.notify(f"Prove sospese: {reason}. Completate {len(data['completed'])}/6; "
                       "ripresa automatica delle sole mancanti quando tornano energia e condizioni favorevoli.")
    save(folder, data)
    return False


def tick(folder):
    with (folder / "campaign.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        data = json.loads((folder / "campaign.json").read_text())
        now = time.time()
        if data.get("active"):
            finish_attempt(folder, data, now)
            save(folder, data)
            return
        if not data.get("enabled"):
            cleanup(folder)
            return
        local = datetime.fromtimestamp(now, ROME)
        if not 9 <= local.hour < 16:
            data.update(status="attesa", reason="fuori finestra diurna 09–16", ready_since=None, last_check=now)
            save(folder, data)
            return
        if now < data.get("retry_after", 0):
            return
        snap = thermal.snapshot()
        reason = start_blocker(snap, now)
        if not reason:
            with sqlite3.connect("file:"+str(thermal.DB)+"?mode=ro", uri=True, timeout=5) as db:
                last = db.execute("SELECT ts FROM samples ORDER BY ts DESC LIMIT 1").fetchone()
            if not last or now-last[0] > 120:
                reason = "raccolta ECM non aggiornata"
        gap = now-data["last_check"] if data.get("last_check") is not None else None
        if reason or gap is None or gap > 180:
            data["ready_since"] = None
        data.update(last_check=now, reason=reason, status="attesa", last_values={k:snap[k] for k in ("soc", "pv", "load", "zg", "zn")})
        if reason:
            save(folder, data)
            return
        data["ready_since"] = data["ready_since"] or now
        if now-data["ready_since"] < STABLE_S:
            data["reason"] = "verifica condizioni stabili per almeno 5 minuti"
            save(folder, data)
            return
        with thermal.LOCK_FILE.open("w") as test_lock:
            try:
                fcntl.flock(test_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                data["reason"] = "altra sessione di prove attiva"
                save(folder, data)
                return
        pending = pending_codes(data)
        if not pending:
            data.update(enabled=False, status="completata")
            save(folder, data)
            cleanup(folder)
            return
        active = folder / ("attempt-"+local.strftime("%Y%m%d-%H%M%S"))
        active.mkdir()
        data.update(active=str(active), status="avvio", ready_since=None)
        data["attempts"].append({"folder": str(active), "started": now, "codes": pending})
        save(folder, data)
        with (active / "runner.log").open("a") as log:
            process = subprocess.Popen([
                sys.executable, str(Path(thermal.__file__).resolve()), "run", str(active),
                "--minutes", "30", "--plan", "consumption", "--codes", ",".join(map(str, pending)),
                "--wait-minutes", "0"], stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
        data["attempts"][-1]["pid"] = process.pid
        save(folder, data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("init", "tick", "status"))
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    if args.mode == "init":
        print(json.dumps(initialize(args.folder), ensure_ascii=False))
    elif args.mode == "status":
        print((args.folder / "campaign.json").read_text())
    else:
        try:
            tick(args.folder)
        except Exception as exc:
            print(thermal.stamp(), "controller:", type(exc).__name__, str(exc), flush=True)
            raise
