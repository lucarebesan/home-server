#!/usr/bin/env python3
"""Confronta la configurazione server Higeco col backup, senza scrivere."""

import argparse
import json

from recover_vpn import BACKUP, server_call
from renew import GatewayClient, credentials, program_lock, quiet_logout


RUNTIME_FIELDS = {"server", "port", "vpn"}


def compare(before, current):
    if not isinstance(before, list) or not isinstance(current, list) or len(before) != 4 or len(current) != 4:
        raise RuntimeError("Array server inatteso")
    differences = []
    for slot, (old, new) in enumerate(zip(before, current), start=1):
        if not isinstance(old, dict) or not isinstance(new, dict):
            raise RuntimeError("Slot server inatteso")
        for field in sorted(old.keys() | new.keys()):
            if old.get(field) != new.get(field):
                differences.append({"slot": slot, "field": field,
                                    "runtime": field in RUNTIME_FIELDS})
    return differences


def audit():
    before = json.loads(BACKUP.read_text(encoding="utf-8"))["config"]
    client = GatewayClient()
    with program_lock():
        client.login("admin", credentials()["admin"])
        try:
            current = server_call(client, "getServerConf")
            status = server_call(client, "getServerStatus")
        finally:
            quiet_logout(client)
    differences = compare(before, current)
    return {
        "configured_fields_equal": not any(not item["runtime"] for item in differences),
        "changed_fields": differences,
        "vpn_option_enabled": current[0].get("abilVpn") == 1,
        "gateway_reports_server_connected": isinstance(status, list) and bool(status)
                                            and status[0].get("successo") == 1,
        "status_field_names": sorted(status[0]) if isinstance(status, list) and status
                              and isinstance(status[0], dict) else [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps(audit(), sort_keys=True))


if __name__ == "__main__":
    main()
