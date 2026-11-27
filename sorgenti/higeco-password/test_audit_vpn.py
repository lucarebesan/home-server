import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import audit_vpn


class AuditTests(unittest.TestCase):
    def test_one_session_and_only_field_names_in_report(self):
        original = [{"abilVpn": 1, "confServer": "private.example", "server": "private.example"}, {}, {}, {}]
        current = [{"abilVpn": 1, "confServer": "private.example", "server": "192.0.2.1"}, {}, {}, {}]
        calls = []

        class FakeClient:
            def login(self, name, password):
                calls.append("login")

        def fake_server_call(client, action):
            calls.append(action)
            return current if action == "getServerConf" else [{"successo": 1}]

        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "before.json"
            backup.write_text(json.dumps({"config": original}))
            with patch.object(audit_vpn, "BACKUP", backup), \
                 patch.object(audit_vpn, "GatewayClient", FakeClient), \
                 patch.object(audit_vpn, "credentials", return_value={"admin": "secret"}), \
                 patch.object(audit_vpn, "program_lock", return_value=nullcontext()), \
                 patch.object(audit_vpn, "server_call", side_effect=fake_server_call), \
                 patch.object(audit_vpn, "quiet_logout", side_effect=lambda client: calls.append("logout")):
                report = audit_vpn.audit()

        self.assertEqual(calls, ["login", "getServerConf", "getServerStatus", "logout"])
        self.assertTrue(report["configured_fields_equal"])
        self.assertTrue(report["vpn_option_enabled"])
        self.assertTrue(report["gateway_reports_server_connected"])
        self.assertEqual(report["changed_fields"], [{"slot": 1, "field": "server", "runtime": True}])
        self.assertNotIn("private.example", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
