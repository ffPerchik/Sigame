import json
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("HOST_ID", "1")

if "yaml" not in sys.modules:
    try:
        __import__("yaml")
    except ModuleNotFoundError:
        fake_yaml = types.ModuleType("yaml")
        fake_yaml.safe_load = json.load
        sys.modules["yaml"] = fake_yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot import quest


class QuestReloadTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "stages.json"
        self.old_state = (
            quest.QUEST_FILE,
            quest._QUEST,
            quest._QUEST_MTIME_NS,
            quest._FAILED_MTIME_NS,
            quest._NEXT_AUTO_CHECK,
        )
        quest.QUEST_FILE = str(self.path)
        quest._QUEST = None
        quest._QUEST_MTIME_NS = None
        quest._FAILED_MTIME_NS = None
        quest._NEXT_AUTO_CHECK = 0.0

    def tearDown(self):
        (
            quest.QUEST_FILE,
            quest._QUEST,
            quest._QUEST_MTIME_NS,
            quest._FAILED_MTIME_NS,
            quest._NEXT_AUTO_CHECK,
        ) = self.old_state
        self.temp_dir.cleanup()

    def _write(self, content):
        self.path.write_text(content, encoding="utf-8")
        now = time.time_ns()
        os.utime(self.path, ns=(now, now))
        quest._NEXT_AUTO_CHECK = 0.0

    def test_automatic_reload_and_safe_fallback(self):
        self._write(json.dumps({"stages": {"one": {"mode": "auto"}}}))
        self.assertIn("one", quest.load()["stages"])

        self._write(json.dumps({"stages": {"two": {"mode": "info"}}}))
        self.assertIn("two", quest.load()["stages"])

        self._write("{broken json")
        self.assertIn("two", quest.load()["stages"])
        ok, error = quest.reload_from_disk()
        self.assertFalse(ok)
        self.assertIn("Error", error)
        self.assertIn("two", quest.load()["stages"])

    def test_manual_reload_reports_success(self):
        self._write(json.dumps({"stages": {"manual": {"mode": "gate"}}}))
        ok, details = quest.reload_from_disk()
        self.assertTrue(ok)
        self.assertIn("стадий: 1", details)
        self.assertEqual(quest.get_stage("manual")["mode"], "gate")

    def test_update_command_is_host_only(self):
        source = (REPO_ROOT / "bot" / "bot.py").read_text(encoding="utf-8")
        self.assertIn('HostFilter(), Command("update", "reload")', source)
        self.assertIn("quest.reload_from_disk()", source)


if __name__ == "__main__":
    unittest.main()
