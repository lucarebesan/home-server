"""Verifica offline del ripristino: nessuna richiesta reale al gateway."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import recover_vpn


class RecoveryTests(unittest.TestCase):
    def test_restore_uses_one_login_and_preserves_server_name(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "before.json"
            original = {"abilVpn": 1, "confServer": "cloud.example",
                        "confPort": 443, "server": "cloud.example", "port": 443}
            backup.write_text(json.dumps({"config": [original]}))
            current = [dict(original, abilVpn=0, server="192.0.2.10"), {}, {}, {}]
            calls = []

            class FakeClient:
                def login(self, name, password):
                    calls.append(("login", name))

                def call(self, action):
                    calls.append(("user", action))

            def fake_server_call(client, action, payload=None):
                calls.append(("server", action))
                if action == "getServerConf":
                    return current
                if action == "saveServerConf":
                    self.assertEqual(payload[0]["server"], "cloud.example")
                    self.assertEqual(payload[0]["port"], 443)
                    current[0] = dict(payload[0])
                    return {}
                if action == "getServerStatus":
                    return [{"successo": 1}]
                raise AssertionError(action)

            with patch.object(recover_vpn, "BACKUP", backup), \
                 patch.object(recover_vpn, "GatewayClient", FakeClient), \
                 patch.object(recover_vpn, "credentials", return_value={"admin": "secret"}), \
                 patch.object(recover_vpn, "server_call", side_effect=fake_server_call):
                recover_vpn.restore_once()

            self.assertEqual(calls.count(("login", "admin")), 1)
            self.assertEqual(calls.count(("server", "saveServerConf")), 1)
            self.assertEqual(calls[-1], ("user", "logoutUser"))


if __name__ == "__main__":
    unittest.main()
