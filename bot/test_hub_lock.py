"""Гейт хаба: узел N6 недоступен, пока не пройдены N1–N5."""
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

from bot import db, texts
from bot import bot as botmod


class HubLockTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = db.DB_PATH
        db.DB_PATH = str(Path(self.temp_dir.name) / "quest.db")
        db.init_db()
        db.register(42, "player", "Player", "hub")

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    def test_prerequisite_nodes_always_unlocked(self):
        status = db.nodes_status(42)
        for node in db.PREREQUISITE_NODES:
            if node in db.LOCKED_VISIBLE_NODES:
                self.assertFalse(db.is_node_unlocked(node, status))
            else:
                self.assertTrue(db.is_node_unlocked(node, status))

    def test_n6_stays_locked_until_all_five_done(self):
        for node in ("N1", "N2", "N3", "N4"):
            db.mark_node_done(42, node)
            self.assertFalse(db.is_node_unlocked("N6", db.nodes_status(42)))
        db.mark_node_done(42, "N5")
        self.assertTrue(db.is_node_unlocked("N6", db.nodes_status(42)))

    def test_node_pick_block_rejects_n6_before_prereqs(self):
        self.assertEqual(
            botmod.node_pick_block(42, "N6"),
            texts.NODE_LOCKED.format(node="N6"),
        )
        self.assertEqual(
            botmod.node_pick_block(42, "N4"),
            texts.NODE_LOCKED.format(node="N4"),
        )
        self.assertIsNone(botmod.node_pick_block(42, "N3"))

    def test_node_pick_block_allows_n6_after_prereqs(self):
        for node in db.PREREQUISITE_NODES:
            db.mark_node_done(42, node)
        self.assertIsNone(botmod.node_pick_block(42, "N6"))

    def test_node_pick_block_rejects_done_and_unknown(self):
        db.mark_node_done(42, "N1")
        self.assertEqual(botmod.node_pick_block(42, "N1"), texts.NODE_ALREADY_DONE)
        self.assertEqual(botmod.node_pick_block(42, "N9"), texts.NODE_NOT_FOUND)

    def _render_hub(self):
        import asyncio
        from unittest.mock import AsyncMock

        sent = {}

        async def run():
            botmod.bot.send_message = AsyncMock(
                side_effect=lambda uid, text, reply_markup=None: sent.update(
                    text=text, kb=reply_markup
                )
            )
            await botmod._send_hub(42)

        asyncio.run(run())
        return sent

    def test_hub_hides_n6_entirely_until_prereqs_done(self):
        sent = self._render_hub()
        self.assertNotIn("ТАЙНИК", sent["text"])
        buttons = [
            b.callback_data
            for row in sent["kb"].inline_keyboard
            for b in row
        ]
        self.assertNotIn("node:N6", buttons)
        self.assertNotIn("node:N4", buttons)
        self.assertIn("node:N3", buttons)
        self.assertIn("🔒  4. ОДИН КАДР", sent["text"])

        for node in db.PREREQUISITE_NODES:
            db.mark_node_done(42, node)
        sent = self._render_hub()
        self.assertIn("★  6. ТАЙНИК", sent["text"])
        self.assertIn(texts.HUB_LINE_FINAL.split("{")[0].strip(), sent["text"])
        buttons = [
            b.callback_data
            for row in sent["kb"].inline_keyboard
            for b in row
        ]
        self.assertIn("node:N6", buttons)


if __name__ == "__main__":
    unittest.main()
