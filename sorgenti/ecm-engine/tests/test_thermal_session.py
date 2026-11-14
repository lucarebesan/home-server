"""Arresto energetico e ripristino: nessun comando a un impianto reale."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest


@unittest.skipUnless(os.name == "posix", "il runner usa lock POSIX sul server Linux")
class ThermalSessionTest(unittest.TestCase):
    def check_stop(self, reason):
        spec = importlib.util.spec_from_file_location(
            "thermal_test", os.environ.get("THERMAL_SESSION_SOURCE", str(Path(__file__).parents[1] / "scripts/thermal_session.py")))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        clock = [1800000000.0]
        module.time = types.SimpleNamespace(
            time=lambda: clock[0], sleep=lambda s: clock.__setitem__(0, clock[0]+s))
        initial = {k: "off" for k in module.WRITERS}
        initial.update({k: "0" for k in module.SENSORS})
        initial.update(soc="41", pv="5000", load="1000", grid="0", zg="21", zn="21",
                       ceiling="23.5", cp_fan="OFF", cp_comp="OFF", split_on="SPENTO",
                       cp_mode="RISCALDAMENTO", split_mode="RISCALDAMENTO", split_fan="ALTA",
                       split_set="29", cp_set="17", acs_set="55", manual="AUTO",
                       auto_tests="off", acs_test="off")
        initial["automation.nilan_write"] = "on"
        initial["automation.10_ecm_inverno"] = "on"
        calls, count = [], [0]

        def snapshot():
            count[0] += 1
            if reason == "waiting":
                return dict(initial, soc="40")
            if count[0] == 1:
                return dict(initial)
            snap = dict(initial, split_on="ACCESO", split_fan="MEDIA")
            for entity in module.WRITERS:
                snap[entity] = "off"
            snap["soc" if reason == "battery" else "pv"] = "40" if reason == "battery" else "0"
            return snap

        module.snapshot = snapshot
        module.write = lambda *args: calls.append(("write", *args))
        module.service = lambda *args: calls.append(("service", *args))
        module.notify = lambda *args: None
        module.cleanup_watch = lambda *args: None
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module.DB, module.LOCK_FILE = root / "engine.db", root / "test.lock"
            with sqlite3.connect(module.DB) as db:
                db.executescript(
                    "CREATE TABLE tests(id INTEGER PRIMARY KEY,code INTEGER,durata_min INTEGER,"
                    "origine TEXT,inizio INTEGER,fine INTEGER,esito TEXT);"
                    "CREATE TABLE samples(ts INTEGER PRIMARY KEY,code INTEGER,valido INTEGER,test_id INTEGER);")
            expected = {"battery": "batteria", "pv": "FV insufficiente", "waiting": "condizioni iniziali"}[reason]
            with self.assertRaisesRegex(RuntimeError, expected), contextlib.redirect_stdout(io.StringIO()):
                module.run(root / "session", 40, True, wait_minutes=1)
            if reason == "waiting":
                self.assertEqual(calls, [])
                self.assertFalse((root / "session/session.json").exists())
                return
            saved = json.loads((root / "session/session.json").read_text())
            self.assertTrue(saved["restored"])
            enabled = [x[3]["entity_id"] for x in calls if x[:3] == ("service", "automation", "turn_on")]
            self.assertEqual(enabled, ["automation.10_ecm_inverno", "automation.nilan_write"])
            self.assertIn(("write", 1999108, "Id3", 0), calls)
            with sqlite3.connect(module.DB) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM tests WHERE fine IS NULL").fetchone()[0], 0)
            self.assertEqual(clock[0]-1800000000, 0 if reason == "battery" else 120)

    def test_battery_limit_stops_and_restores(self):
        self.check_stop("battery")

    def test_pv_shortfall_stops_after_two_minutes_and_restores(self):
        self.check_stop("pv")

    def test_waiting_does_not_suspend_automations(self):
        self.check_stop("waiting")


if __name__ == "__main__":
    unittest.main()
