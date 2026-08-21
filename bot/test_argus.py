import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.argus import format_line
from bot.timed_messages import normalize_messages, send_messages, wait_before


class TimedMessagesTests(unittest.IsolatedAsyncioTestCase):
    def test_format_line_uses_real_timestamp_shape(self):
        now = datetime(2026, 8, 22, 23, 41, 7, 123456, tzinfo=timezone.utc)
        self.assertEqual(
            format_line("NETWORK INTERFACE: ACTIVE", now),
            "[23:41:07.123] ARGVS-1001 // NETWORK INTERFACE: ACTIVE",
        )

    def test_multiline_argus_item_is_split_into_messages(self):
        items = normalize_messages([
            {"speaker": "argus", "text": "ONE\nTWO", "delay": 0.5},
            {"text": "обычный\nмногострочный", "delay": 1.0},
        ])
        self.assertEqual([item.text for item in items], ["ONE", "TWO", "обычный\nмногострочный"])
        self.assertEqual([item.delay for item in items], [0.5, 0.5, 1.0])

    async def test_each_delay_happens_before_that_exact_message(self):
        sent = []
        sleeps = []
        current = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)

        async def send(text):
            sent.append((current, text))

        async def sleep(delay):
            nonlocal current
            sleeps.append(delay)
            current += timedelta(seconds=delay)

        await send_messages(
            [
                {"text": "Женя", "delay": 1.0},
                {"speaker": "argus", "text": "ONE", "delay": 0.5},
                {"speaker": "argus", "text": "TWO", "delay": 2.0},
            ],
            send,
            sleep=sleep,
            now_factory=lambda: current,
        )

        self.assertEqual(sleeps, [1.0, 0.5, 2.0])
        self.assertEqual(sent[0], (datetime(2026, 8, 22, 12, 0, 1, tzinfo=timezone.utc), "Женя"))
        self.assertEqual(sent[1][0], datetime(2026, 8, 22, 12, 0, 1, 500000, tzinfo=timezone.utc))
        self.assertEqual(sent[1][1], "[12:00:01.500] ARGVS-1001 // ONE")
        self.assertEqual(sent[2][0], datetime(2026, 8, 22, 12, 0, 3, 500000, tzinfo=timezone.utc))
        self.assertEqual(sent[2][1], "[12:00:03.500] ARGVS-1001 // TWO")

    def test_quest_uses_generic_message_delays(self):
        stages = (REPO_ROOT / "bot" / "quest" / "stages.yaml").read_text(encoding="utf-8")
        self.assertNotIn("argus_delay:", stages)
        self.assertNotIn("\n    argus:", stages)
        self.assertIn("messages:", stages)
        self.assertIn("speaker: argus", stages)
        self.assertIn("delay: 0.5", stages)

    async def test_stage_delay_waits_before_main_message(self):
        sleeps = []

        async def sleep(delay):
            sleeps.append(delay)

        await wait_before(0.75, sleep=sleep)
        await wait_before(0, sleep=sleep)
        self.assertEqual(sleeps, [0.75])


if __name__ == "__main__":
    unittest.main()
