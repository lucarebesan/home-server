"""Prove termiche autorizzate, temporanee, indipendenti dalla connessione SSH.

Eseguire in processo separato con guardia cron `watch SESSION` ogni minuto.
Un servizio systemd utente senza Linger termina alla chiusura della sessione.
Non crea automazioni HA e non modifica le regole del motore ECM.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time
from datetime import datetime
import urllib.request


BASE = "http://127.0.0.1:8123"
TOKEN = Path.home() / ".config/ecm/ha_token"
DB = Path.home() / "ecm-engine/data/engine.db"
LOCK_FILE = Path.home() / "ecm-thermal-session.lock"
PLAN = [(0, 2, 80), (0, 1, 70), (2, 1, 74), (2, 2, 84),
        (2, 3, 94), (3, 3, 95), (3, 2, 85), (3, 1, 75)]
WRITERS = [
    "automation.nilan_write", "automation.10_ecm_inverno",
    "automation.05_ecm_acs_manager", "automation.06_ecm_humidity_override",
    "automation.07_ecm_ricambio_aria_minimo_2",
    "automation.ecm_acs_minimo_bollitore_basso_cp_heat_v2",
    "automation.ecm_acs_sessione_09_novembre_ore_12",
]
SENSORS = {
    "zg": "sensor.ecm_zona_giorno_temperatura_media",
    "zn": "sensor.ecm_zona_notte_temperatura_media",
    "ext": "sensor.ecm_temperatura_esterna_affidabile",
    "soc": "sensor.growatt_inverter_growatt_battery_soc",
    "pv": "sensor.growatt_inverter_growatt_pv_power_total",
    "load": "sensor.growatt_inverter_growatt_total_load_power",
    "grid": "sensor.growatt_inverter_growatt_total_import_power",
    "cp_w": "sensor.compactp_potenza_attiva",
    "split_w": "sensor.toshiba_potenza_attiva",
    "split_on": "sensor.toshiba_on_off_unita",
    "split_mode": "sensor.toshiba_modo_unita",
    "split_fan": "sensor.toshiba_velocita_ventilatore",
    "split_set": "sensor.toshiba_setpoint",
    "cp_fan": "sensor.compactp_ventilazione_selezionata",
    "cp_comp": "sensor.compactp_compressore",
    "cp_mode": "sensor.compactp_modo_funzionale_selezionato",
    "cp_set": "sensor.compactp_setpoint_aria",
    "acs_set": "sensor.compactp_setpoint_acs_resistenza",
    "acs_comp_set": "sensor.compactp_setpoint_acs_compressore",
    "t11": "sensor.compactp_t11_temperatura_bollitore_parte_alta",
    "t12": "sensor.compactp_t12_temperatura_bollitore_parte_bassa",
    "res": "sensor.compactp_resistenza_elettrica_acs",
    "manual": "input_select.ecm_manuale",
    "auto_tests": "switch.ecm_engine_prove_automatiche",
    "acs_test": "input_boolean.ecm_acs_prova_caldo_attiva",
    "ceiling": "input_number.ecm_inverno_massimo_accumulo",
}


def request(path, body=None):
    req = urllib.request.Request(
        BASE + path, data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + TOKEN.read_text().strip(),
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)


def service(domain, action, data):
    return request(f"/api/services/{domain}/{action}", data)


def write(plugin, command, value):
    service("shell_command", "nilan_write", {
        "plugin": str(plugin), "id": command, "value": value, "scale": "1"})


def snapshot():
    entities = dict(SENSORS, **{e: e for e in WRITERS})
    fields = [repr(k) + ":states(" + repr(e) + ")" for k, e in entities.items()]
    fields.append("'cp_changed':(expand('sensor.compactp_compressore') | map(attribute='last_changed') "
                  "| map('as_timestamp') | first | default(none))")
    template = "{{ {" + ",".join(fields) + "}|tojson }}"
    value = request("/api/template", {"template": template})
    return json.loads(value) if isinstance(value, str) else value


def num(value):
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else None
    except (ValueError, TypeError):
        return None


def stamp(ts=None):
    return datetime.fromtimestamp(ts or time.time()).isoformat(timespec="seconds")


def save(folder, data):
    tmp = folder / "session.tmp"
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(folder / "session.json")


def event(folder, kind, **data):
    row = {"time": stamp(), "event": kind, **data}
    with (folder / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False), flush=True)


def notify(message):
    service("persistent_notification", "create", {
        "notification_id": "ecm_thermal_session", "title": "Prove termiche CP / Toshiba",
        "message": message})


def watch_tag(folder):
    return "ECM_THERMAL_" + hashlib.sha256(str(folder).encode()).hexdigest()[:12]


def cleanup_watch(folder):
    current = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if current.returncode != 0:
        return
    lines = current.stdout.splitlines()
    kept = [line for line in lines if watch_tag(folder) not in line]
    if kept != lines:
        subprocess.run(["crontab", "-"], input="\n".join(kept)+"\n", text=True, check=True)


def watch(folder):
    """Guardia cron indipendente dalla chat e dal processo principale."""
    session = folder / "session.json"
    if session.exists() and json.loads(session.read_text()).get("restored"):
        cleanup_watch(folder)
        return
    worker_path = folder / "worker.json"
    if not worker_path.exists():
        return
    worker = json.loads(worker_path.read_text())
    process = Path("/proc") / str(worker["pid"])
    try:
        alive = (Path("/proc/sys/kernel/random/boot_id").read_text().strip() == worker["boot"]
                 and str(folder).encode() in (process / "cmdline").read_bytes())
    except OSError:
        alive = False
    if alive and time.time() < worker["deadline"]:
        return
    if alive:
        os.kill(worker["pid"], signal.SIGTERM)
        time.sleep(5)
    if session.exists():
        restore(folder)
    else:
        notify("Prove non avviate: attesa terminata. Gestione ordinaria rimasta attiva.")
        cleanup_watch(folder)


def record_phase(folder, data, start, end, code, result):
    """Solo test già CHIUSI: nessun test aperto interferisce con la guardia ECM."""
    key = str(int(start))
    if key in data.setdefault("recorded", {}):
        return
    with sqlite3.connect(DB, timeout=10) as db:
        cursor = db.execute(
            "INSERT INTO tests(code,durata_min,origine,inizio,fine,esito) VALUES(?,?,?,?,?,?)",
            (code, data["minutes"], "manuale", int(start), int(end), result))
        test_id = cursor.lastrowid
        db.execute("UPDATE samples SET test_id=? WHERE ts>=? AND ts<? AND code=? "
                   "AND valido=1 AND test_id IS NULL", (test_id, int(start), int(end), code))
    data["recorded"][key] = test_id
    save(folder, data)
    event(folder, "fase_registrata", code=code, test_id=test_id, result=result)


def restore(folder):
    if not (folder / "session.json").exists():
        return
    with (folder / "restore.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = json.loads((folder / "session.json").read_text())
        if data.get("restored"):
            return
        initial = data["initial"]
        errors = []
        commands = [(1999108, "Id3", 0), (1999494, "Id14", 0),
                    (1999494, "Id15", float(initial["cp_set"])),
                    (1999667, "Id1", float(initial["acs_set"])),
                    (1999108, "Id6", float(initial["split_set"])),
                    (1999108, "Id5", {"BASSA": 1, "MEDIA": 2, "ALTA": 3,
                                       "AUTOMATICA": 0}[initial["split_fan"]])]
        for plugin, command, value in commands:
            try:
                write(plugin, command, value)
            except Exception as exc:
                errors.append(f"{plugin}/{command}: {type(exc).__name__}")
        # Solo le automazioni inizialmente accese; WRITE per ultima.
        suspended = [e for e in data.get("suspended", []) if e != "automation.nilan_write"]
        for entity in suspended + (["automation.nilan_write"] if "automation.nilan_write" in data.get("suspended", []) else []):
            try:
                service("automation", "turn_on", {"entity_id": entity})
            except Exception as exc:
                errors.append(entity + ": " + type(exc).__name__)
        data.update(restored=not errors, restored_at=stamp(), restore_errors=errors,
                    status="ripristinata" if not errors else "errore_ripristino")
        save(folder, data)
        event(folder, "ripristino", errors=errors)
        notify("Prove terminate. Gestione ordinaria ripristinata." if not errors else
               "Prove terminate; verificare il ripristino: " + "; ".join(errors))
        if errors:
            raise RuntimeError("ripristino incompleto")
        cleanup_watch(folder)


def run(folder, minutes, combined, wait_minutes=45):
    folder.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (folder / "session.json").exists():
            raise RuntimeError("sessione già esistente: non riutilizzare la cartella")
        (folder / "worker.json").write_text(json.dumps({
            "pid": os.getpid(), "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "deadline": time.time() + (wait_minutes + minutes * (8 if combined else 2) + 5) * 60,
        }), encoding="utf-8")
        wait_until = time.time() + wait_minutes * 60
        waiting_notice = False
        while True:
            initial = snapshot()
            ready = (num(initial["soc"]) is not None and num(initial["soc"]) > 40
                     and num(initial["pv"]) is not None and num(initial["load"]) is not None
                     and num(initial["pv"]) >= num(initial["load"])
                     and (initial["cp_comp"] == "OFF" or
                          (initial["cp_comp"] == "ON" and num(initial.get("cp_changed")) is not None
                           and time.time()-num(initial["cp_changed"]) >= 900))
                     and initial["split_on"] in ("SPENTO", "OFF"))
            if ready:
                break
            (folder / "waiting.json").write_text(json.dumps({
                "time": stamp(), "until": stamp(wait_until), "values": initial}), encoding="utf-8")
            if not waiting_notice:
                notify("Prove programmate: attesa batteria almeno 41%, FV sufficiente e fine del minimo "
                       "di 15 minuti dell'eventuale ciclo CP. "
                       "La gestione ordinaria resta attiva durante l'attesa.")
                waiting_notice = True
            if time.time() >= wait_until:
                notify("Prove non avviate: condizioni iniziali non raggiunte entro 45 minuti. Gestione ordinaria attiva.")
                raise RuntimeError("condizioni iniziali non raggiunte; nessuna automazione sospesa")
            time.sleep(min(60, max(0, wait_until-time.time())))
        if initial["manual"] != "AUTO" or initial["auto_tests"] != "off" or initial["acs_test"] != "off":
            raise RuntimeError("un altro comando manuale o una prova è attiva")
        if initial["cp_comp"] not in ("ON", "OFF") or initial["split_on"] not in ("SPENTO", "OFF"):
            raise RuntimeError("precondizione: stato CP valido e Toshiba fermo")
        if initial["cp_mode"] != "RISCALDAMENTO" or initial["split_mode"] != "RISCALDAMENTO":
            raise RuntimeError("modi macchina diversi da HEAT")
        for key in ("zg", "zn", "ceiling", "cp_set", "acs_set", "split_set"):
            if num(initial[key]) is None:
                raise RuntimeError("dato iniziale non valido: " + key)
        if num(initial["soc"]) is None or num(initial["soc"]) <= 40 or (num(initial["pv"]) or 0) <= 0:
            raise RuntimeError("avvio rinviato: batteria deve superare il 40% e FV disponibile")
        ceiling = min(23.5, float(initial["ceiling"]))
        if max(float(initial["zg"]), float(initial["zn"])) >= ceiling:
            raise RuntimeError("limite termico già raggiunto")
        plan = PLAN if combined else PLAN[:2]
        data = {"created": stamp(), "minutes": minutes, "plan": plan, "initial": initial,
                "suspended": [e for e in WRITERS if initial[e] == "on"],
                "status": "preparazione", "ceiling": ceiling}
        save(folder, data)
        active = None
        try:
            for entity in data["suspended"]:
                service("automation", "turn_off", {"entity_id": entity, "stop_actions": True})
            # Sospensione della resistenza; il setpoint originale è nel ripristino.
            write(1999667, "Id1", 38)
            write(1999494, "Id14", 0)
            write(1999494, "Id15", 17)
            write(1999108, "Id6", 29)
            previous_cp = 0
            for index, (cp, split, code) in enumerate(plan):
                if cp != previous_cp:
                    write(1999494, "Id15", 23.5 if cp else 17)
                    write(1999494, "Id14", cp)
                    previous_cp = cp
                write(1999108, "Id5", split)
                if index == 0:
                    write(1999108, "Id3", 1)
                start = time.time()
                deadline = start + minutes * 60
                active = (start, code)
                label = f"CP {'HEAT V' + str(cp) if cp else 'OFF V0'} + SPLIT HEAT V{split}"
                data.update(status="in_corso", phase=index+1, label=label, phase_start=start,
                            phase_end=deadline, planned_end=deadline+(len(plan)-index-1)*minutes*60)
                save(folder, data)
                event(folder, "inizio_fase", phase=index+1, label=label, end=stamp(deadline))
                notify(f"Fase {index+1}/{len(plan)}: **{label}** fino alle **{stamp(deadline)[11:16]}**. "
                       f"Fine sequenza prevista {stamp(data['planned_end'])[11:16]}. Sole presente: resa netta osservata.")
                warned = set()
                invalid_since = None
                mismatch_since = None
                energy_bad_since = None
                cp_bad_since = None
                while time.time() < deadline:
                    snap = snapshot()
                    event(folder, "campione", phase=index+1, values=snap)
                    zones = [num(snap[k]) for k in ("zg", "zn")]
                    if None in zones:
                        invalid_since = invalid_since or time.time()
                        if time.time() - invalid_since > 300:
                            raise RuntimeError("temperature non disponibili per oltre 5 minuti")
                    else:
                        invalid_since = None
                        if max(zones) >= ceiling:
                            raise RuntimeError("limite termico raggiunto")
                    if any((num(snap[k]) or 0) >= 60 for k in ("t11", "t12")):
                        raise RuntimeError("limite bollitore raggiunto")
                    if snap["manual"] != "AUTO" or any(snap[e] != "off" for e in data["suspended"]):
                        raise RuntimeError("intervento manuale o automazione riattivata")
                    if num(snap["soc"]) is not None and num(snap["soc"]) <= 40:
                        raise RuntimeError("batteria al 40% o inferiore: riprendere un altro giorno")
                    energy_changed = (num(snap["pv"]) is None or num(snap["load"]) is None
                                      or num(snap["soc"]) is None
                                      or num(snap["pv"]) < num(snap["load"]))
                    if energy_changed:
                        energy_bad_since = energy_bad_since or time.time()
                        if time.time()-energy_bad_since >= 120:
                            raise RuntimeError("FV insufficiente per due minuti: riprendere un altro giorno")
                    else:
                        energy_bad_since = None
                    if energy_changed and "energia" not in warned:
                        warned.add("energia")
                        event(folder, "avviso_energia", soc=snap["soc"], pv=snap["pv"], grid=snap["grid"])
                        notify(f"Verifica energia durante **{label}**: batteria {snap['soc']}%, "
                               f"FV {snap['pv']} W, carico {snap['load']} W. "
                               "Arresto se il FV resta insufficiente per due minuti.")
                    cp_matches = snap["cp_fan"] == ("OFF" if not cp else f"STEP {cp}")
                    cp_matches = cp_matches and snap["cp_comp"] == ("ON" if cp else "OFF")
                    if cp_matches:
                        cp_bad_since = None
                    else:
                        cp_bad_since = cp_bad_since or time.time()
                        if time.time()-cp_bad_since >= 300:
                            raise RuntimeError("CP non conferma la configurazione da cinque minuti")
                    expected_fan = {1: "BASSA", 2: "MEDIA", 3: "ALTA"}[split]
                    matches = snap["split_on"] in ("ACCESO", "ON") and snap["split_fan"] == expected_fan
                    if matches:
                        mismatch_since = None
                    else:
                        mismatch_since = mismatch_since or time.time()
                        if time.time()-mismatch_since > 180:
                            raise RuntimeError("Toshiba non conferma il comando da oltre 3 minuti")
                    time.sleep(max(0, min(60, deadline-time.time())))
                record_phase(folder, data, start, deadline, code, "completata")
                active = None
            data["result"] = "completata"
        except BaseException as exc:
            data["result"] = str(exc) or type(exc).__name__
            if active:
                record_phase(folder, data, active[0], time.time(), active[1], "interrotta: " + data["result"])
            event(folder, "interruzione", reason=data["result"])
            raise
        finally:
            save(folder, data)
            restore(folder)


def interrupted(signum, frame):
    raise RuntimeError("arresto del servizio")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("run", "restore", "watch"))
    parser.add_argument("folder", type=Path)
    parser.add_argument("--minutes", type=int, choices=(30, 40), default=40)
    parser.add_argument("--combined", action="store_true")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    if args.mode == "restore":
        restore(args.folder)
    elif args.mode == "watch":
        watch(args.folder)
    else:
        try:
            run(args.folder, args.minutes, args.combined)
        finally:
            if not (args.folder / "session.json").exists():
                cleanup_watch(args.folder)
