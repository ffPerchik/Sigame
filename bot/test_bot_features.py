import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("HOST_ID", "1")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot import db
from bot.hints import stage_hints


class HintSequenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = db.DB_PATH
        db.DB_PATH = str(Path(self.temp_dir.name) / "quest.db")
        db.init_db()
        db.register(42, "player", "Player", "N3_pig")
        db.set_banked(42, 2)

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    def test_hint_formats_are_normalized(self):
        self.assertEqual(stage_hints(None), [])
        self.assertEqual(stage_hints({"hint": " одна "}), ["одна"])
        self.assertEqual(
            stage_hints({"hints": [" первая ", "", "вторая"], "hint": "старая"}),
            ["первая", "вторая"],
        )

    def test_hints_are_consumed_in_order_without_extra_charges(self):
        self.assertEqual(db.consume_hint(42, "N3_pig", 2), ("ok", 1, 0))
        self.assertEqual(db.consume_hint(42, "N3_pig", 2), ("ok", 0, 1))
        self.assertEqual(db.consume_hint(42, "N3_pig", 2), ("exhausted", 0, 2))
        self.assertEqual(db.get_player(42)["banked"], 0)

    def test_no_balance_and_reset_are_handled(self):
        self.assertEqual(db.consume_hint(42, "N4_signs", 1), ("ok", 1, 0))
        self.assertEqual(db.consume_hint(42, "N5_bin", 1), ("ok", 0, 0))
        self.assertEqual(db.consume_hint(42, "N6_a1", 1), ("no_balance", 0, 0))

        db.set_banked(42, 1)
        db.reset_hint_usage(42)
        self.assertEqual(db.consume_hint(42, "N3_pig", 2), ("ok", 0, 0))


class HostFeatureWiringTests(unittest.TestCase):
    def test_direct_messages_and_answer_relay_are_wired(self):
        source = (REPO_ROOT / "bot" / "bot.py").read_text(encoding="utf-8")
        self.assertIn('Command("msg", "message")', source)
        self.assertIn("HOST_MESSAGE_PLAYER", source)
        self.assertIn("ANSWER_ATTEMPT_HOST", source)
        self.assertIn('db.log_event(uid, "answer_attempt"', source)


if __name__ == "__main__":
    unittest.main()
