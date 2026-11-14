"""Politica della campagna: riprese, soglie e rispetto dei comandi manuali."""
import importlib.util
import os
import json
import sqlite3
from pathlib import Path
import sys
import unittest
import tempfile
import types
from unittest.mock import patch


@unittest.skipUnless(os.name == "posix", "controller del server Linux")
class CampaignTest(unittest.TestCase):
    def setUp(self):
        source = Path(os.environ.get("THERMAL_CAMPAIGN_SOURCE", str(Path(__file__).parents[1] / "scripts/thermal_campaign.py")))
        sys.path.insert(0, str(source.parent))
        spec = importlib.util.spec_from_file_location("campaign_test", source)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.now = 1800000000
        self.snap = {e: "on" for e in self.m.thermal.WRITERS}
        self.snap.update(season="INVERNO", manual="AUTO", acs_test="off", auto_tests="off",
                         free_cooling="DISATTIVATO", soc="41", pv="5000", load="1200",
                         zg="21", zn="21", t11="50", t12="35", cp_w="0", split_w="0",
                         ceiling="23.5", cp_mode="RISCALDAMENTO", split_mode="RISCALDAMENTO",
                         split_on="SPENTO", split_fan="BASSA", cp_comp="OFF")
        for k in ("soc", "pv", "load", "zg", "zn", "t11", "t12", "gateway"):
            self.snap["reported_"+k] = self.now

    def test_start_requires_energy_freshness_and_manual_authority(self):
        self.assertIsNone(self.m.start_blocker(self.snap, self.now))
        for change in ({"soc": "40"}, {"pv": "2000"}, {"reported_pv": self.now-181}, {"reported_gateway": self.now-181},
                       {"automation.nilan_write": "off"}, {"manual": "E70"},
                       {"zg": "23.1"}, {"load": "0"}):
            with self.subTest(change=change):
                self.assertIsNotNone(self.m.start_blocker(dict(self.snap, **change), self.now))

    def test_partial_20_retries_but_28_and_29_are_skipped(self):
        state = {"plan": self.m.thermal.CONSUMPTION_PLAN, "completed": {}}
        def payload(code, minutes):
            return dict(code=code, minutes=30, start=1000, end=1000+minutes*60,
                        result="completata con tolleranza", original_result="interrotta: FV insufficiente",
                        accepted=True, coverage={"good": minutes, "operating": minutes})
        self.m.absorb_results(state, {"phase_results": {"a": payload(74, 20), "b": payload(75, 28), "c": payload(84, 29)}})
        self.assertEqual(set(state["completed"]), {"75", "84"})
        self.assertEqual(self.m.pending_codes(state), [74, 85, 95, 94])

    def test_cp_minimum_and_season_are_respected(self):
        snap = dict(self.snap, cp_comp="ON", cp_changed=self.now-899)
        self.assertIsNotNone(self.m.start_blocker(snap, self.now))
        snap["cp_changed"] = self.now-900
        self.assertIsNone(self.m.start_blocker(snap, self.now))
        self.assertIsNotNone(self.m.start_blocker(dict(self.snap, season="ESTATE"), self.now))

    def test_dispatch_requires_five_minutes_and_launches_all_pending_in_order(self):
        clock = [self.m.datetime(2026, 11, 15, 10, 0, tzinfo=self.m.ROME).timestamp()]
        self.m.time = types.SimpleNamespace(time=lambda: clock[0])
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "campaign"
            self.m.initialize(folder)
            db_path = Path(tmp) / "engine.db"
            with sqlite3.connect(db_path) as db:
                db.execute("CREATE TABLE samples(ts INTEGER)")
            with patch.object(self.m.thermal, "DB", db_path), \
                 patch.object(self.m.thermal, "LOCK_FILE", Path(tmp)/"run.lock"), \
                 patch.object(self.m.thermal, "snapshot", side_effect=lambda: self.snap), \
                 patch.object(self.m.subprocess, "Popen", return_value=types.SimpleNamespace(pid=12345)) as spawn:
                for minute in range(6):
                    for key in ("soc", "pv", "load", "gateway"):
                        self.snap["reported_"+key] = clock[0]
                    with sqlite3.connect(db_path) as db:
                        db.execute("DELETE FROM samples")
                        db.execute("INSERT INTO samples VALUES(?)", (int(clock[0]),))
                    self.m.tick(folder)
                    self.assertEqual(spawn.call_count, int(minute == 5))
                    clock[0] += 60
                command = spawn.call_args.args[0]
                self.assertEqual(command[command.index("--codes")+1], "74,75,85,95,84,94")
                self.assertEqual(command[command.index("--minutes")+1], "30")

    def test_energy_stop_waits_to_retry_but_manual_override_pauses_campaign(self):
        for reason, enabled in (("FV insufficiente per due minuti", True), ("intervento manuale", False)):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp) / "campaign"
                data = self.m.initialize(folder)
                active = folder / "attempt"
                active.mkdir()
                data.update(active=str(active), attempts=[{"started": self.now-1800}])
                (active/"session.json").write_text(json.dumps({"restored": True, "result": reason, "phase_results": {}}))
                with patch.object(self.m.thermal, "watch"), patch.object(self.m.thermal, "notify"), patch.object(self.m, "cleanup"):
                    self.m.finish_attempt(folder, data, self.now)
                self.assertEqual(data["enabled"], enabled)
                self.assertIsNone(data["active"])
                if enabled:
                    self.assertEqual(data["retry_after"], self.now+900)


if __name__ == "__main__":
    unittest.main()
