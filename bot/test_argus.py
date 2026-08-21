import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.argus import format_line, normalize_lines, send_lines


class ArgusMessagesTests(unittest.IsolatedAsyncioTestCase):
    def test_format_line_uses_real_timestamp_shape(self):
        now = datetime(2026, 8, 22, 23, 41, 7, 123456, tzinfo=timezone.utc)
        self.assertEqual(
            format_line("NETWORK INTERFACE: ACTIVE", now),
            "[23:41:07.123] ARGVS-1001 // NETWORK INTERFACE: ACTIVE",
        )

    def test_multiline_items_are_split(self):
        self.assertEqual(normalize_lines(["ONE\nTWO", "", " THREE "]), ["ONE", "TWO", "THREE"])

    async def test_each_line_is_separate_with_half_second_delay(self):
        sent = []
        sleeps = []
        current = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)

        async def send(text):
            sent.append(text)

        async def sleep(delay):
            nonlocal current
            sleeps.append(delay)
            current += timedelta(seconds=delay)

        def now_factory():
            return current

        await send_lines(
            ["ONE", "TWO", "THREE"],
            send,
            delay=0.5,
            sleep=sleep,
            now_factory=now_factory,
        )

        self.assertEqual(sleeps, [0.5, 0.5])
        self.assertEqual(len(sent), 3)
        self.assertEqual(sent[0], "[12:00:00.000] ARGVS-1001 // ONE")
        self.assertEqual(sent[1], "[12:00:00.500] ARGVS-1001 // TWO")
        self.assertEqual(sent[2], "[12:00:01.000] ARGVS-1001 // THREE")


if __name__ == "__main__":
    unittest.main()
