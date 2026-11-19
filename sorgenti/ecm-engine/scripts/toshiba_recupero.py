"""Confronto una tantum del recupero Toshiba tra 20,0 e 20,5 °C.

Usa soltanto la richiesta di velocità e il timer di permanenza della 10.
Le automazioni di riscaldamento, ACS e ricambio restano attive.
"""

import argparse
import fcntl
import json
import math
from datetime import datetime
from pathlib import Path
import subprocess
import time

from thermal_session import LOCK_FILE, request, service


SETPOINT = 22.5
START = 20.0
TARGET = 20.5
MAX_SECONDS = 2 * 3600
FAN = "input_number.toshiba_ventilatore"
HOLD = "input_datetime.ecm_inverno_ultima_scelta"
TAG = "# ECM_TOSHIBA_RECUPERO_20261119"
CAMPAIGN = Path.home() / "ecm-tests/consumi-auto-6/campaign.json"
ENTITIES = {
    "zg": "sensor.ecm_zona_giorno_temperatura_media_10m",
    "zn": "sensor.ecm_zona_notte_temperatura_media_10m",
    "outside": "sensor.ecm_temperatura_esterna_affidabile",
    "sun": "sun.sun",
    "write": "automation.nilan_write",
    "winter": "automation.10_ecm_inverno",
    "auto": "input_select.ecm_manuale",
    "season": "input_select.stagione",
    "phase": "sensor.ecm_fascia_climatica_attiva",
    "night": "input_datetime.nilan_serale",
    "heating": "input_boolean.ecm_riscaldamento_ambiente_attivo",
    "requested_on": "input_boolean.toshiba_climatizzatore",
    "on": "sensor.toshiba_on_off_unita",
    "mode": "sensor.toshiba_modo_unita",
    "fan": "sensor.toshiba_velocita_ventilatore",
    "requested_fan": FAN,
    "hold": HOLD,
    "set": "sensor.toshiba_setpoint",
    "requested_set": "input_number.toshiba_setpoint",
    "watts": "sensor.toshiba_potenza_attiva",
    "cp": "sensor.compactp_compressore",
    "cp_fan": "sensor.compactp_ventilazione_selezionata",
    "cp_res": "sensor.compactp_resistenza_elettrica_acs",
    "ceiling": "input_number.ecm_inverno_massimo_accumulo",
    "soc": "sensor.growatt_inverter_growatt_battery_soc",
    "pv": "sensor.growatt_inverter_growatt_pv_power_total",
    "load": "sensor.growatt_inverter_growatt_total_load_power",
    "engine_tests": "switch.ecm_engine_prove_automatiche",
    "acs_test": "input_boolean.ecm_acs_prova_caldo_attiva",
}
EXPECTED = {
    "write": "on", "winter": "on", "auto": "AUTO", "season": "INVERNO",
    "phase": "GIORNO", "heating": "on", "requested_on": "on",
    "on": "ACCESO", "mode": "RISCALDAMENTO", "cp": "OFF", "cp_fan": "OFF",
    "cp_res": "OFF", "sun": "above_horizon", "engine_tests": "off", "acs_test": "off",
}
FAN_NAMES = {2: "MEDIA", 3: "ALTA"}


def snapshot():
    fields = [repr(key) + ":states(" + repr(entity) + ")" for key, entity in ENTITIES.items()]
    fields.append("'batch':as_timestamp(states.sensor.nilan_batch.last_reported, 0)")
    fields.append("'outside_age':state_attr('sensor.ecm_temperatura_esterna_affidabile','eta_minuti')")
    fields.append("'elevation':state_attr('sun.sun','elevation')")
    result = request("/api/template", {"template": "{{ {" + ",".join(fields) + "}|tojson }}"})
    return json.loads(result) if isinstance(result, str) else result


def numeric(row, key):
    result = float(row[key])
    if not math.isfinite(result):
        raise ValueError(key)
    return result


def guard(row, now):
    for key, expected in EXPECTED.items():
        if row.get(key) != expected:
            return f"{key}={row.get(key)} (atteso {expected})"
    try:
        if not 0 <= now - numeric(row, "batch") <= 120:
            return "telemetria gateway non recente"
        if numeric(row, "soc") <= 40 or numeric(row, "pv") < numeric(row, "load"):
            return "batteria o FV insufficienti"
        if numeric(row, "set") != SETPOINT or numeric(row, "requested_set") != SETPOINT:
            return "setpoint diverso da 22,5 °C"
        if max(numeric(row, "zg"), numeric(row, "zn")) >= min(23.5, numeric(row, "ceiling")):
            return "massimo termico raggiunto"
        if numeric(row, "watts") < 0:
            return "potenza non valida"
    except (KeyError, ValueError, TypeError):
        return "telemetria indispensabile non valida"
    return None


def start_blocker(row, now, reference):
    problem = guard(row, now)
    if problem:
        return problem
    try:
        local = datetime.fromtimestamp(now)
        night = datetime.combine(local.date(), datetime.strptime(row["night"], "%H:%M:%S").time())
        if night.timestamp() - now < MAX_SECONDS + 180:
            return "finestra diurna residua insufficiente"
        if not 19.90 <= numeric(row, "zg") <= START:
            return "zona giorno fuori dalla partenza 19,90–20,00 °C"
        if not 0 <= numeric(row, "outside_age") <= 60:
            return "temperatura esterna di partenza non recente"
        outside = numeric(row, "outside")
        elevation = numeric(row, "elevation")
        if reference and (abs(outside - reference["outside"]) > 1
                          or abs(elevation - reference["elevation"]) > 10):
            return "esterno o altezza del sole diversi dalla V2"
    except (KeyError, ValueError, TypeError):
        return "dati di partenza mancanti"
    return None


def crossing(previous, current, threshold):
    """Interpolazione tra misure (secondi, temperatura media, watt)."""
    fraction = (threshold - previous[1]) / (current[1] - previous[1])
    return (previous[0] + fraction * (current[0] - previous[0]), threshold,
            previous[2] + fraction * (current[2] - previous[2]))


def compare(v2, v3):
    minutes = 100 * (v3["seconds"] / v2["seconds"] - 1)
    energy = 100 * (v3["kwh"] / v2["kwh"] - 1)
    return {"delta_tempo_percento": round(minutes, 2), "delta_kwh_percento": round(energy, 2),
            "v3_conviene": v3["seconds"] + 30 < v2["seconds"] and v3["kwh"] < v2["kwh"]}


def save(folder, status):
    path = folder / "stato.tmp"
    path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
    path.replace(folder / "stato.json")


def running_campaign():
    # La campagna parallela scrive questo stato sotto lo stesso lock termico.
    return CAMPAIGN.exists() and json.loads(CAMPAIGN.read_text()).get("active")


def full_test(folder, status, first, speed, until):
    old_hold = first["hold"]
    lease = None
    started = time.time()
    previous = begin = None
    total_ws = 0.0
    result = None
    try:
        while time.time() < until:
            row = snapshot()
            now = time.time()
            problem = guard(row, now)
            if problem:
                raise RuntimeError(problem)
            zg = numeric(row, "zg")
            if lease is not None and (row["hold"] != lease or numeric(row, "requested_fan") != speed):
                raise RuntimeError("comando o velocità modificati da un altro controllo")
            if row["fan"] == FAN_NAMES[speed]:
                point = (now, zg, numeric(row, "watts"))
                if previous and now - previous[0] > 90:
                    raise RuntimeError("buco nel campionamento")
                if begin is None:
                    if zg == START:
                        begin = point
                    elif previous and previous[1] < START < zg:
                        begin = crossing(previous, point, START)
                    elif zg > START:
                        raise RuntimeError("soglia iniziale superata prima della conferma di velocità")
                    if begin:
                        previous = begin
                if begin and previous and point[0] > previous[0]:
                    endpoint = crossing(previous, point, TARGET) if zg >= TARGET else point
                    total_ws += (endpoint[0] - previous[0]) * (endpoint[2] + previous[2]) / 2
                    if zg >= TARGET:
                        result = {"speed": speed, "start": begin[0], "end": endpoint[0],
                                  "seconds": round(endpoint[0] - begin[0], 1),
                                  "kwh": round(total_ws / 3_600_000, 5),
                                  "outside": numeric(first, "outside"),
                                  "elevation": numeric(first, "elevation")}
                        if result["seconds"] <= 0 or result["kwh"] <= 0:
                            raise RuntimeError("misura termica o energetica non valida")
                        break
                previous = point
            elif begin or now - started > 180:
                raise RuntimeError("velocità fisica Toshiba non confermata")
            if lease is None or now - datetime.fromisoformat(lease).timestamp() >= 300:
                lease = datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S")
                service("input_datetime", "set_datetime", {"entity_id": HOLD, "datetime": lease})
                if numeric(row, "requested_fan") != speed:
                    service("input_number", "set_value", {"entity_id": FAN, "value": speed})
            status.update(reason=f"V{speed}, zona giorno {zg:.2f} °C", updated=now)
            save(folder, status)
            time.sleep(30)
        if result is None:
            raise RuntimeError("20,5 °C non raggiunti nel tempo di prova")
        return result
    finally:
        if lease is not None and snapshot().get("hold") == lease:
            service("input_datetime", "set_datetime", {"entity_id": HOLD, "datetime": old_hold})


def remove_schedule():
    current = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if current.returncode == 0:
        lines = current.stdout.splitlines()
        preserved = [line for line in lines if not line.rstrip().endswith(TAG)]
        if preserved != lines:
            subprocess.run(["crontab", "-"], input="\n".join(preserved) + "\n",
                           text=True, check=True)


def init(folder):
    folder.mkdir(mode=0o700)
    now = time.time()
    save(folder, {"status": "attesa", "reason": "attesa prima finestra compatibile",
                  "created": now, "updated": now, "expires": now + 7 * 86400,
                  "results": {}, "attempts": []})


def tick(folder, check_only=False):
    path = folder / "stato.json"
    with (folder / "recupero.lock").open("a") as own_lock:
        try:
            fcntl.flock(own_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        status = json.loads(path.read_text(encoding="utf-8"))
        now = time.time()
        if status["status"] in ("completato", "scaduto") or now >= status["expires"]:
            if check_only:
                print(status["status"] if now < status["expires"] else "termine scaduto")
                return
            if status["status"] != "completato":
                status.update(status="scaduto", updated=now)
                save(folder, status)
            remove_schedule()
            return
        results = status["results"]
        speed = 2 if "2" not in results else 3
        row = snapshot()
        problem = start_blocker(row, now, results.get("2"))
        if check_only:
            print(problem or f"condizioni compatibili con V{speed}")
            return
        if status["status"] == "in_corso":
            status.update(status="attesa", retry_after=now + 900,
                          reason="processo interrotto, attesa scadenza del mantenimento")
        if now < status.get("retry_after", 0) or problem:
            status.update(reason=problem or status["reason"], updated=now)
            save(folder, status)
            return
        with LOCK_FILE.open("a") as shared_lock:
            try:
                fcntl.flock(shared_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            if running_campaign():
                return
            status.update(status="in_corso", speed=speed, updated=now)
            save(folder, status)
            try:
                result = full_test(folder, status, row, speed, min(now + MAX_SECONDS, status["expires"]))
            except Exception as exc:
                status.update(status="attesa", retry_after=time.time() + 1800, reason=str(exc))
                status["attempts"].append({"speed": speed, "start": now, "reason": str(exc)})
            else:
                results[str(speed)] = result
                status.update(status="attesa", retry_after=time.time() + 1800,
                              reason=f"V{speed} completata")
                if len(results) == 2:
                    status.update(status="completato", comparison=compare(results["2"], results["3"]))
            finally:
                status["updated"] = time.time()
                save(folder, status)
            if status["status"] == "completato":
                remove_schedule()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="verifica i requisiti in sola lettura")
    modes.add_argument("--init", action="store_true", help="inizializza una nuova sessione per sette giorni")
    args = parser.parse_args()
    if args.init:
        init(args.folder)
    else:
        tick(args.folder, args.check)
