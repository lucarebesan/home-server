#!/usr/bin/env python3
"""Valuta la Posta in arrivo Gmail; sposta solo con --apply-uid esplicito."""

from __future__ import annotations

import argparse
import hashlib
import imaplib
import json
import os
import re
import sqlite3
import stat
import sys
from datetime import datetime, timezone
from email.parser import BytesHeaderParser
from email.policy import default
from pathlib import Path

BASE = Path.home() / ".local/share/mail-svuota"
SECRET = Path.home() / ".config/mail-svuota/app-password"
ACCOUNT = "ing.rebesan@gmail.com"
HOST = "imap.gmail.com"
RULES = Path(__file__).with_name("rules.json")
META_RE = {
    "uid": re.compile(rb"\bUID (\d+)\b"),
    "msgid": re.compile(rb"\bX-GM-MSGID (\d+)\b"),
    "flags": re.compile(rb"\bFLAGS \(([^)]*)\)"),
    "labels": re.compile(rb"\bX-GM-LABELS \(([^)]*)\)"),
}


def load_rules() -> tuple[dict, str]:
    raw = RULES.read_bytes()
    rules = json.loads(raw)
    if rules["destination"] != "SVUOTA":
        raise ValueError("La destinazione deve essere SVUOTA")
    return rules, hashlib.sha256(raw).hexdigest()[:16]


def read_secret() -> str:
    info = SECRET.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("Credenziale: proprietario o permessi non sicuri; servono 600")
    value = SECRET.read_text(encoding="utf-8").strip().replace(" ", "")
    if not value:
        raise ValueError("Credenziale vuota")
    return value


def parse_fetch(data: list) -> tuple[dict, bytes]:
    parts = [item for item in data if isinstance(item, tuple)]
    if len(parts) != 1 or len(parts[0]) != 2:
        raise ValueError("Risposta FETCH inattesa")
    meta, header = parts[0]
    values = {}
    for key, pattern in META_RE.items():
        match = pattern.search(meta)
        if not match:
            raise ValueError(f"FETCH senza {key}")
        values[key] = match.group(1)
    return values, header


def tokens(raw: bytes) -> set[str]:
    # Le etichette protette sono nomi ASCII semplici. Se un nome complesso
    # impedisce il parsing, l'operazione viene bloccata dal controllo sotto.
    return {part.strip('"').casefold() for part in raw.decode("utf-8", "replace").split()}


def classify(headers: bytes, labels: set[str], rules: dict) -> tuple[str, str, str, str]:
    msg = BytesHeaderParser(policy=default).parsebytes(headers)
    sender = str(msg.get("from", ""))
    subject = str(msg.get("subject", ""))
    haystack = subject.casefold()
    sender_lower = sender.casefold()
    protected = {name.casefold() for name in rules["protected_labels"]}
    if labels & protected:
        return "keep", "etichetta protetta", sender, subject
    if any(msg.get(field) for field in ("in-reply-to", "references")):
        return "keep", "parte di una conversazione", sender, subject
    if any(
        bool(re.search(r"\bpec\b", haystack)) if term == "pec" else term in haystack
        for term in rules["protected_subject_terms"]
    ):
        return "keep", "oggetto operativo o personale", sender, subject
    if any(term in sender_lower for term in rules["protected_sender_terms"]):
        return "keep", "mittente protetto", sender, subject
    bulk = bool(msg.get("list-unsubscribe") or msg.get("list-id"))
    marketing_sender = any(
        term in sender_lower for term in rules["marketing_sender_terms"]
    )
    strong_promo = any(
        term in haystack for term in rules["strong_promo_subject_terms"]
    )
    weak_promo = any(
        term in haystack for term in rules["weak_promo_subject_terms"]
    )
    if strong_promo and (bulk or marketing_sender):
        return "candidate", "promozione commerciale", sender, subject
    if weak_promo and bulk and marketing_sender:
        return "candidate", "invito commerciale massivo", sender, subject
    if not bulk:
        return "review", "manca indicatore di invio massivo", sender, subject
    return "review", "invio massivo senza promozione certa", sender, subject


def db_open() -> sqlite3.Connection:
    BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(BASE, 0o700)
    path = BASE / "state.sqlite3"
    db = sqlite3.connect(path)
    os.chmod(path, 0o600)
    db.execute(
        """CREATE TABLE IF NOT EXISTS decisions (
            uidvalidity TEXT NOT NULL,
            uid INTEGER NOT NULL,
            rule_version TEXT NOT NULL,
            gmail_msgid TEXT NOT NULL,
            decision TEXT NOT NULL,
            reason TEXT NOT NULL,
            sender TEXT NOT NULL,
            subject TEXT NOT NULL,
            flags TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            PRIMARY KEY (uidvalidity, uid, rule_version)
        )"""
    )
    return db


def uid_fetch(conn: imaplib.IMAP4_SSL, uid: int) -> tuple[dict, bytes]:
    status, data = conn.uid(
        "FETCH",
        str(uid),
        "(UID X-GM-MSGID FLAGS X-GM-LABELS "
        "BODY.PEEK[HEADER.FIELDS (FROM SUBJECT LIST-ID LIST-UNSUBSCRIBE IN-REPLY-TO REFERENCES)])",
    )
    if status != "OK":
        raise RuntimeError(f"FETCH fallito per UID {uid}")
    return parse_fetch(data)


def current_labels(conn: imaplib.IMAP4_SSL, uid: int) -> tuple[str, set[str], set[str]]:
    status, data = conn.uid("FETCH", str(uid), "(UID X-GM-MSGID FLAGS X-GM-LABELS)")
    if status != "OK" or not data:
        raise RuntimeError(f"Verifica fallita per UID {uid}")
    # FETCH senza literal: la risposta è una sola riga bytes.
    meta = next((part for part in data if isinstance(part, bytes) and b"X-GM-MSGID" in part), None)
    if meta is None:
        raise RuntimeError(f"Metadati assenti per UID {uid}")
    values = {}
    for key in ("msgid", "flags", "labels"):
        match = META_RE[key].search(meta)
        if not match:
            raise RuntimeError(f"Metadati incompleti per UID {uid}")
        values[key] = match.group(1)
    return values["msgid"].decode(), tokens(values["labels"]), tokens(values["flags"])


def apply_move(conn: imaplib.IMAP4_SSL, uid: int, msgid: str, rules: dict) -> None:
    before_id, labels, flags = current_labels(conn, uid)
    if before_id != msgid or not labels or labels & {
        name.casefold() for name in rules["protected_labels"]
    }:
        raise RuntimeError(f"Etichette o identità cambiate per UID {uid}")
    if "\\inbox" not in labels:
        raise RuntimeError(f"UID {uid} non è più in Posta in arrivo")
    status, _ = conn.uid("STORE", str(uid), "+X-GM-LABELS", "(SVUOTA)")
    if status != "OK":
        raise RuntimeError(f"Impossibile aggiungere SVUOTA per UID {uid}")
    interim_id, interim_labels, interim_flags = current_labels(conn, uid)
    if (interim_id != msgid or "svuota" not in interim_labels
            or interim_flags != flags):
        raise RuntimeError(f"Verifica dopo aggiunta SVUOTA fallita per UID {uid}")
    status, _ = conn.uid("STORE", str(uid), "-X-GM-LABELS", "(\\Inbox)")
    if status != "OK":
        raise RuntimeError(f"Impossibile togliere INBOX per UID {uid}")
    # Dopo la rimozione il vecchio UID non è più visibile in INBOX.
    status, _ = conn.select("SVUOTA", readonly=True)
    if status != "OK":
        raise RuntimeError("Impossibile verificare SVUOTA")
    status, data = conn.uid("SEARCH", None, "X-GM-MSGID", msgid)
    if status != "OK" or not data or len(data[0].split()) != 1:
        raise RuntimeError(f"Messaggio {msgid} non trovato univocamente in SVUOTA")
    moved_uid = int(data[0].split()[0])
    after_id, after_labels, after_flags = current_labels(conn, moved_uid)
    if (after_id != msgid or "svuota" not in after_labels
            or "\\inbox" in after_labels or after_flags != flags):
        raise RuntimeError(f"Verifica finale fallita per UID {uid}")
    status, _ = conn.select("INBOX", readonly=False)
    if status != "OK":
        raise RuntimeError("Impossibile tornare a INBOX")


def scan(apply_uid: int | None, limit: int | None) -> None:
    apply = apply_uid is not None
    rules, version = load_rules()
    db = db_open()
    conn = imaplib.IMAP4_SSL(HOST, 993, timeout=20)
    try:
        conn.login(ACCOUNT, read_secret())
        status, capability_data = conn.capability()
        if status != "OK" or not any(
            b"X-GM-EXT-1" in part.split() for part in capability_data if part
        ):
            raise RuntimeError("Le estensioni IMAP Gmail non sono disponibili")
        if apply:
            status, boxes = conn.list("", "SVUOTA")
            if status != "OK" or not boxes or not any(
                box and box.rsplit(b" ", 1)[-1].strip(b'"') == b"SVUOTA"
                for box in boxes
            ):
                raise RuntimeError("Etichetta SVUOTA non visibile in IMAP")
        status, _ = conn.select("INBOX", readonly=not apply)
        if status != "OK":
            raise RuntimeError("Impossibile selezionare INBOX")
        _, validity_data = conn.response("UIDVALIDITY")
        if not validity_data or not validity_data[0]:
            raise RuntimeError("UIDVALIDITY assente")
        validity = validity_data[0].decode()
        status, data = conn.uid("SEARCH", None, "ALL")
        if status != "OK":
            raise RuntimeError("Ricerca INBOX fallita")
        uids = [int(item) for item in data[0].split()]
        if apply and apply_uid not in uids:
            raise RuntimeError(f"UID {apply_uid} non presente in INBOX")
        counts = {"keep": 0, "review": 0, "candidate": 0, "moved": 0, "cached": 0}
        selected = [apply_uid] if apply else uids[:limit]
        for uid in selected:
            previous = db.execute(
                "SELECT decision FROM decisions WHERE uidvalidity=? AND uid=? AND rule_version=?",
                (validity, uid, version),
            ).fetchone()
            if apply and (not previous or previous[0] != "candidate"):
                raise RuntimeError(f"UID {uid} non è un candidato approvabile della simulazione")
            if previous and not apply:
                counts["cached"] += 1
                continue
            values, headers = uid_fetch(conn, uid)
            labels = tokens(values["labels"])
            decision, reason, sender, subject = classify(headers, labels, rules)
            msgid = values["msgid"].decode()
            if apply and decision != "candidate":
                raise RuntimeError(f"UID {uid} non è più un candidato: {reason}")
            if apply:
                apply_move(conn, uid, msgid, rules)
                decision = "moved"
            db.execute(
                """INSERT OR REPLACE INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (validity, uid, version, msgid, decision, reason, sender,
                 subject, values["flags"].decode("utf-8", "replace"),
                 datetime.now(timezone.utc).isoformat()),
            )
            db.commit()
            counts[decision] += 1
        print(json.dumps({"inbox": len(uids), "processed": sum(counts.values()),
                          "rules": version, "mode": "apply" if apply else "dry-run",
                          **counts}, ensure_ascii=False))
    finally:
        try:
            conn.logout()
        except Exception:
            pass
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-uid", type=int, help="sposta un solo UID già candidato")
    parser.add_argument("--limit", type=int, help="valuta solo i primi N UID")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit deve essere positivo")
    if args.apply_uid is not None and args.apply_uid < 1:
        parser.error("--apply-uid deve essere positivo")
    if args.apply_uid is not None and args.limit is not None:
        parser.error("--limit non è compatibile con --apply-uid")
    try:
        scan(args.apply_uid, args.limit)
    except (OSError, ValueError, RuntimeError, imaplib.IMAP4.error) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
