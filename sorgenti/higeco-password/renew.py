#!/usr/bin/env python3
"""Rinnova le password Higeco, conservando e ripristinando le regole originali."""

import argparse
import fcntl
import getpass
import gzip
import json
import os
import stat
import sys
import tempfile
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import date
from pathlib import Path


GATEWAY = "http://192.168.1.171"
SECRET = Path.home() / ".config/higeco-password/credentials.json"
STATE_DIR = Path.home() / ".local/state/higeco-password"
JOURNAL = STATE_DIR / "restore-rules.json"
STATE = STATE_DIR / "renewal.json"
RULE_KEYS = (
    "passExpire", "minLen", "maxLen", "useNumChar", "useUpChar",
    "useLowChar", "useSpecChar", "excludeUsername",
)
RELAX_KEYS = ("useNumChar", "useUpChar", "useLowChar", "useSpecChar", "excludeUsername")
FIRST_DUE = date(2027, 1, 1)


class RenewalError(Exception):
    pass


def atomic_json(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def remove_journal():
    JOURNAL.unlink()
    directory_fd = os.open(STATE_DIR, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def credentials():
    if SECRET.is_symlink() or not SECRET.is_file() or stat.S_IMODE(SECRET.stat().st_mode) != 0o600:
        raise RenewalError("Credenziali assenti o permessi diversi da 600")
    value = read_json(SECRET)
    if not all(isinstance(value.get(name), str) and value[name] for name in ("admin", "user")):
        raise RenewalError("Credenziali incomplete")
    return value


def setup_credentials():
    if SECRET.exists():
        raise RenewalError("Credenziali già presenti: nessuna sovrascrittura automatica")
    value = {}
    for name in ("admin", "user"):
        first = getpass.getpass(f"Password attuale di {name}: ")
        second = getpass.getpass(f"Ripeti password di {name}: ")
        if not first or first != second:
            raise RenewalError(f"Password di {name} vuota o non coincidente")
        value[name] = first
    atomic_json(SECRET, value)
    print("Credenziali salvate sul mini PC con permessi 600")


@contextmanager
def program_lock():
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    fd = os.open(STATE_DIR / ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RenewalError("Un altro rinnovo è già in corso") from exc
        yield
    finally:
        os.close(fd)


class GatewayClient:
    def __init__(self, base=GATEWAY):
        self.base = base
        self.cookie = None
        self.sn = None

    def _post(self, fields):
        body = urllib.parse.urlencode(fields).encode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if self.cookie:
            headers["Cookie"] = f"gwc={self.cookie}"
        request = urllib.request.Request(self.base + "/cgi-bin/userCgi", body, headers)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read()
        except Exception as exc:
            raise RenewalError("Gateway non raggiungibile") from exc
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        try:
            result = json.loads(raw)
            row = result["DATI"][0]
            if result.get("ERR") != 0 or row.get("ERR") != 0:
                raise RenewalError(f"Gateway ha rifiutato {row.get('act', 'richiesta')}")
            return row.get("DATI", {})
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RenewalError("Risposta del gateway non valida") from exc

    def login(self, name, password):
        self.cookie = None
        data = self._post({
            "p": password, "u": name,
            "query": json.dumps([{"act": "getStatus"}], separators=(",", ":")),
        })
        if data.get("auth") != 1 or not data.get("k") or not data.get("sn"):
            raise RenewalError(f"Login {name} non valido o password scaduta")
        self.cookie = data["k"]
        self.sn = data["sn"]
        return data

    def call(self, act, data=None):
        if not self.cookie or not self.sn:
            raise RenewalError("Sessione mancante")
        query = [{"act": act, "sn": self.sn, "idReq": act, "DATI": data or {}}]
        return self._post({"query": json.dumps(query, separators=(",", ":"))})


def rule_values(raw):
    if not isinstance(raw, dict) or any(key not in raw for key in RULE_KEYS):
        raise RenewalError("Regole password incomplete: nessuna modifica")
    try:
        return {key: int(raw[key]) for key in RULE_KEYS}
    except (TypeError, ValueError) as exc:
        raise RenewalError("Regole password non numeriche") from exc


def user_ids(client):
    raw = client.call("getUser")
    users = raw.get("userArr") if isinstance(raw, dict) else None
    if not isinstance(users, list):
        raise RenewalError("Elenco utenti non valido")
    found = {item.get("nome"): item.get("id") for item in users if isinstance(item, dict)}
    if any(not found.get(name) for name in ("user", "admin")):
        raise RenewalError("ID user/admin non trovati")
    return found


def assert_rules(client, wanted):
    actual = rule_values(client.call("getPasswordRules"))
    if actual != rule_values(wanted):
        raise RenewalError("Regole lette diverse da quelle attese")


def restore(client, admin_password):
    if not JOURNAL.exists():
        return False
    original = read_json(JOURNAL)["rules"]
    try:
        try:
            current = rule_values(client.call("getPasswordRules"))
        except RenewalError:
            client.login("admin", admin_password)
            current = rule_values(client.call("getPasswordRules"))
        if current != rule_values(original):
            client.call("setPasswordRules", original)
            assert_rules(client, original)
        remove_journal()
        return True
    except Exception as exc:
        raise RenewalError("Ripristino regole fallito; stato di recupero conservato") from exc


def renew(client, secret):
    if JOURNAL.exists():
        restore(client, secret["admin"])
    client.login("admin", secret["admin"])
    ids = user_ids(client)
    original = client.call("getPasswordRules")
    limits = rule_values(original)
    relaxed = dict(original)
    for key in RELAX_KEYS:
        relaxed[key] = 0
    for name in ("user", "admin"):
        if not limits["minLen"] <= len(secret[name]) <= limits["maxLen"]:
            raise RenewalError(f"Lunghezza password di {name} fuori dai limiti")
    atomic_json(JOURNAL, {"rules": original})
    problem = None
    try:
        client.call("setPasswordRules", relaxed)
        assert_rules(client, relaxed)
        client.call("modPass", {"id": ids["user"], "p": secret["user"]})
        client.call("modPass", {"id": ids["admin"], "p": secret["admin"]})
    except Exception as exc:
        problem = exc
    restore(client, secret["admin"])
    if problem:
        raise problem
    for name in ("admin", "user"):
        GatewayClient(client.base).login(name, secret[name])
    today = date.today()
    atomic_json(STATE, {
        "last_success": today.isoformat(),
        "success_notice_pending": today.isoformat(),
    })
    print("Password di user e admin rinnovate; regole originali ripristinate e verificate")
    retry_success_notice()


def due_today(today):
    if today < FIRST_DUE:
        return False
    month = today.month if today.month % 2 else today.month - 1
    due = date(today.year, month, 1)
    last = read_json(STATE).get("last_success", "") if STATE.exists() else ""
    return last < due.isoformat()


def next_due(after):
    for year in (after.year, after.year + 1, after.year + 2):
        for month in (1, 3, 5, 7, 9, 11):
            candidate = date(year, month, 1)
            if candidate >= FIRST_DUE and candidate > after:
                return candidate
    raise RenewalError("Prossima data di rinnovo non calcolabile")


def send_phone(message):
    token_file = Path.home() / ".config/ecm/ha_token"
    if not token_file.is_file():
        return False
    try:
        token = token_file.read_text(encoding="utf-8").strip()
        body = json.dumps({
            "title": "Rinnovo gateway Higeco",
            "message": message,
        }).encode("utf-8")
        request = urllib.request.Request(
            "http://127.0.0.1:8123/api/services/notify/mobile_app_iphone_luca",
            body,
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5):
            pass
        return True
    except Exception:
        print("Notifica HA non inviata", file=sys.stderr)
        return False


def retry_success_notice():
    if not STATE.exists():
        return
    state = read_json(STATE)
    pending = state.get("success_notice_pending")
    if not pending:
        return
    renewed = date.fromisoformat(pending)
    following = next_due(renewed)
    message = (
        f"Password Higeco di user e admin rinnovate il {renewed:%d/%m/%Y}; "
        f"regole ripristinate. Prossimo rinnovo previsto il {following:%d/%m/%Y}."
    )
    if send_phone(message):
        state.pop("success_notice_pending")
        atomic_json(STATE, state)
        print("Notifica di successo accettata da Home Assistant")


def notify_failure(message):
    send_phone(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--setup", action="store_true", help="Inserisce le password con prompt nascosto")
    group.add_argument("--check", action="store_true", help="Sola lettura: verifica accessi e regole")
    group.add_argument("--renew", action="store_true", help="Rinnovo reale immediato")
    group.add_argument("--scheduled", action="store_true", help="Rinnovo quando dovuto, recupero ogni giorno")
    args = parser.parse_args()
    try:
        with program_lock():
            if args.setup:
                setup_credentials()
                return 0
            secret = credentials()
            client = GatewayClient()
            if args.check and JOURNAL.exists():
                raise RenewalError("Regole da ripristinare: --check non esegue scritture")
            if JOURNAL.exists():
                restore(client, secret["admin"])
                print("Regole originali recuperate")
            if not args.check:
                retry_success_notice()
            if args.check:
                client.login("admin", secret["admin"])
                user_ids(client)
                rule_values(client.call("getPasswordRules"))
                GatewayClient().login("user", secret["user"])
                print("Accessi admin/user e lettura regole riusciti; nessuna modifica")
            elif args.renew or due_today(date.today()):
                renew(client, secret)
            else:
                print("Rinnovo non ancora dovuto")
        return 0
    except Exception as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        if not args.setup and not args.check:
            notify_failure("Rinnovo password Higeco fallito. Controllare il mini PC e le regole password del gateway.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
