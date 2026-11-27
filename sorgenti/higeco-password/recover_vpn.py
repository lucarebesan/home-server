#!/usr/bin/env python3
"""Ripristina una sola volta la VPN Higeco dopo il blocco dei login admin.

Il cron controlla spesso solo un file locale. Ogni tentativo verso il gateway
avviene a distanza di almeno quattro ore e usa un solo login admin, con logout.
"""

import argparse
import fcntl
import gzip
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from renew import GATEWAY, GatewayClient, atomic_json, credentials


STATE_DIR = Path.home() / ".local/state/higeco-password"
STATE = STATE_DIR / "vpn-recovery.json"
BACKUP = STATE_DIR / "vpn-test-before.json"
INTERVAL = 4 * 3600


def server_call(client, action, payload=None):
    query = [{"act": action, "sn": client.sn, "idReq": action, "DATI": payload or {}}]
    body = urllib.parse.urlencode({"query": json.dumps(query, separators=(",", ":"))}).encode()
    request = urllib.request.Request(
        GATEWAY + "/cgi-bin/serverCgi",
        body,
        {"Content-Type": "application/x-www-form-urlencoded", "Cookie": f"gwc={client.cookie}"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        raw = response.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    result = json.loads(raw)
    row = result["DATI"][0]
    if result.get("ERR") != 0 or row.get("ERR") != 0:
        raise RuntimeError(f"Gateway ha rifiutato {action}")
    return row.get("DATI")


def notify_success():
    token = (Path.home() / ".config/ecm/ha_token").read_text().strip()
    body = json.dumps({
        "title": "Gateway Nilan ripristinato",
        "message": "VPN riattivata e collegamento gateway-server attivo. Verifica se i valori Exrg si aggiornano. Le richieste HA restano in pausa.",
    }).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:8123/api/services/notify/mobile_app_iphone_luca",
        body,
        {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


def restore_once():
    original = json.loads(BACKUP.read_text(encoding="utf-8"))["config"][0]
    if original.get("abilVpn") != 1 or not original.get("confServer"):
        raise RuntimeError("Backup VPN non valido")
    client = GatewayClient()
    client.login("admin", credentials()["admin"])
    try:
        current = server_call(client, "getServerConf")
        if not isinstance(current, list) or len(current) != 4:
            raise RuntimeError("Configurazione server inattesa")
        if current[0].get("abilVpn") != 1 or current[0].get("confServer") != original["confServer"]:
            changed = json.loads(json.dumps(current))
            changed[0]["abilVpn"] = 1
            changed[0]["server"] = original["confServer"]
            changed[0]["port"] = original["confPort"]
            server_call(client, "saveServerConf", changed)
        for _ in range(7):
            actual = server_call(client, "getServerConf")
            status = server_call(client, "getServerStatus")
            if (actual[0].get("abilVpn") == 1
                    and actual[0].get("confServer") == original["confServer"]
                    and status[0].get("successo") == 1):
                return
            time.sleep(15)
        raise RuntimeError("VPN riattivata ma Exrg non ancora connesso")
    finally:
        try:
            client.call("logoutUser")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("arm", "scheduled", "status"))
    args = parser.parse_args()
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE_DIR, 0o700)
    lock_fd = os.open(STATE_DIR / ".vpn-recovery.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.mode == "arm":
            if STATE.exists():
                raise RuntimeError("Recupero già armato; nessuna sovrascrittura")
            if not BACKUP.exists():
                raise RuntimeError("Backup VPN mancante")
            state = {"complete": False, "attempts": 0,
                     "next_attempt": time.time() + INTERVAL,
                     "notification_pending": False}
            atomic_json(STATE, state)
            print("Primo tentativo non prima di", datetime.fromtimestamp(state["next_attempt"]).isoformat())
            return
        if not STATE.exists():
            raise RuntimeError("Recupero non armato")
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if args.mode == "status":
            print("complete", state["complete"], "attempts", state["attempts"],
                  "next_attempt", datetime.fromtimestamp(state["next_attempt"]).isoformat(),
                  "notification_pending", state["notification_pending"])
            return
        if state["complete"]:
            if state["notification_pending"]:
                try:
                    notify_success()
                except Exception as exc:
                    print("Notifica da ritentare:", type(exc).__name__)
                else:
                    state["notification_pending"] = False
                    atomic_json(STATE, state)
            return
        if time.time() < state["next_attempt"]:
            return
        # La prossima scadenza viene salvata PRIMA del login: un crash non
        # provoca tentativi ripetuti al giro successivo di cron.
        state["attempts"] += 1
        state["next_attempt"] = time.time() + INTERVAL
        atomic_json(STATE, state)
        try:
            restore_once()
        except Exception as exc:
            print(datetime.now(timezone.utc).isoformat(), "Recupero VPN rinviato:", type(exc).__name__)
            return
        state["complete"] = True
        state["notification_pending"] = True
        atomic_json(STATE, state)
        print(datetime.now(timezone.utc).isoformat(), "VPN riattivata; gateway-server connesso")
        try:
            notify_success()
        except Exception as exc:
            print("Notifica da ritentare:", type(exc).__name__)
        else:
            state["notification_pending"] = False
            atomic_json(STATE, state)
    finally:
        os.close(lock_fd)


if __name__ == "__main__":
    main()
