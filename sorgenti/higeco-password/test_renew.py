import gzip
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch


SOURCE = Path(__file__).with_name("renew.py")
SPEC = importlib.util.spec_from_file_location("higeco_renew", SOURCE)
renew = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renew)


class FakeGateway:
    rules = {}
    events = []
    fail_account = None

    def __init__(self, base=renew.GATEWAY):
        self.base = base
        self.logged_in = False

    def login(self, name, password):
        if password != {"admin": "Admin123!", "user": "simple"}[name]:
            raise renew.RenewalError("Login fallito")
        self.logged_in = True
        self.events.append(("login", name))
        return {"auth": 1}

    def call(self, act, data=None):
        if not self.logged_in:
            raise renew.RenewalError("Sessione assente")
        self.events.append((act, data))
        if act == "getUser":
            return {"userArr": [{"nome": "admin", "id": 1}, {"nome": "user", "id": 2}]}
        if act == "getPasswordRules":
            return dict(self.rules)
        if act == "setPasswordRules":
            type(self).rules = dict(data)
            return {}
        if act == "modPass":
            if any(self.rules[key] for key in renew.RELAX_KEYS):
                raise renew.RenewalError("Regole ancora attive")
            if self.fail_account == data["id"]:
                raise renew.RenewalError("Cambio rifiutato")
            return {}
        raise AssertionError(act)


class RenewalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.saved = (renew.STATE_DIR, renew.JOURNAL, renew.STATE, renew.GatewayClient)
        renew.STATE_DIR = Path(self.temp.name)
        renew.JOURNAL = renew.STATE_DIR / "restore-rules.json"
        renew.STATE = renew.STATE_DIR / "renewal.json"
        renew.GatewayClient = FakeGateway
        self.addCleanup(self.restore_globals)
        FakeGateway.rules = {
            "passExpire": 90, "minLen": 4, "maxLen": 64,
            "useNumChar": 1, "useUpChar": 1, "useLowChar": 1,
            "useSpecChar": 1, "excludeUsername": 1,
        }
        FakeGateway.events = []
        FakeGateway.fail_account = None
        self.secrets = {"admin": "Admin123!", "user": "simple"}

    def restore_globals(self):
        renew.STATE_DIR, renew.JOURNAL, renew.STATE, renew.GatewayClient = self.saved

    def test_both_passwords_one_relaxed_window_then_restore(self):
        original = dict(FakeGateway.rules)
        renew.renew(FakeGateway(), self.secrets)
        self.assertEqual(FakeGateway.rules, original)
        self.assertFalse(renew.JOURNAL.exists())
        self.assertTrue(renew.STATE.exists())
        changes = [event[1]["id"] for event in FakeGateway.events if event[0] == "modPass"]
        self.assertEqual(changes, [2, 1])
        saves = [event for event in FakeGateway.events if event[0] == "setPasswordRules"]
        self.assertEqual(len(saves), 2)

    def test_failure_restores_rules_and_keeps_success_unrecorded(self):
        original = dict(FakeGateway.rules)
        FakeGateway.fail_account = 1
        with self.assertRaises(renew.RenewalError):
            renew.renew(FakeGateway(), self.secrets)
        self.assertEqual(FakeGateway.rules, original)
        self.assertFalse(renew.JOURNAL.exists())
        self.assertFalse(renew.STATE.exists())

    def test_recovery_after_abrupt_interruption(self):
        original = dict(FakeGateway.rules)
        renew.atomic_json(renew.JOURNAL, {"rules": original})
        for key in renew.RELAX_KEYS:
            FakeGateway.rules[key] = 0
        client = FakeGateway()
        self.assertTrue(renew.restore(client, self.secrets["admin"]))
        self.assertEqual(FakeGateway.rules, original)
        self.assertFalse(renew.JOURNAL.exists())

    def test_schedule_catches_missed_first_of_odd_month(self):
        self.assertFalse(renew.due_today(renew.date(2026, 12, 31)))
        self.assertTrue(renew.due_today(renew.date(2027, 1, 1)))
        renew.atomic_json(renew.STATE, {"last_success": "2027-01-03"})
        self.assertFalse(renew.due_today(renew.date(2027, 2, 10)))
        self.assertTrue(renew.due_today(renew.date(2027, 3, 1)))


class ProtocolTests(unittest.TestCase):
    def test_login_cookie_and_modpass_payload(self):
        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.close()

        requests = []

        def fake_open(request, timeout):
            fields = urllib.parse.parse_qs(request.data.decode())
            query = json.loads(fields["query"][0])[0]
            requests.append((request, fields, query))
            data = (
                {"auth": 1, "k": "session123", "sn": "serial", "uid": 1}
                if query["act"] == "getStatus" else {}
            )
            body = {"ERR": 0, "DATI": [{"ERR": 0, "act": query["act"], "DATI": data}]}
            return Response(gzip.compress(json.dumps(body).encode()))

        with patch("urllib.request.urlopen", side_effect=fake_open):
            client = renew.GatewayClient()
            client.login("admin", "Admin123!")
            client.call("modPass", {"id": 2, "p": "simple"})
        self.assertEqual(requests[0][1]["u"], ["admin"])
        self.assertEqual(requests[1][0].get_header("Cookie"), "gwc=session123")
        self.assertEqual(requests[1][2]["DATI"], {"id": 2, "p": "simple"})


if __name__ == "__main__":
    unittest.main()
