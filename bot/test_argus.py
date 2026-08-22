import re
import sys
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.argus import format_line
from bot.timed_messages import normalize_messages, send_messages, send_typewriter, wait_before


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

    async def test_typewriter_adds_one_word_at_a_time(self):
        versions = []

        async def send(partial):
            versions.append(partial)
            return "message"

        async def edit(_message, partial):
            versions.append(partial)

        async def sleep(_delay):
            pass

        await send_typewriter("Привет, это Женя!", send, edit, sleep=sleep)
        self.assertEqual(versions, ["Привет,", "Привет, это", "Привет, это Женя!"])

    async def test_typewriter_does_not_send_whitespace_only_updates(self):
        versions = []

        async def send(partial):
            versions.append(partial)
            return "message"

        async def edit(_message, partial):
            versions.append(partial)

        async def sleep(_delay):
            pass

        await send_typewriter("А Б\nВ", send, edit, sleep=sleep)
        self.assertEqual(versions, ["А", "А Б", "А Б\nВ"])

    async def test_typewriter_edits_one_message_without_trailing_delay(self):
        events = []
        message = object()

        async def send(partial):
            events.append(("send", partial))
            return message

        async def edit(sent_message, partial):
            self.assertIs(sent_message, message)
            events.append(("edit", partial))

        async def sleep(delay):
            events.append(("sleep", delay))

        result = await send_typewriter(
            "ONE TWO THREE",
            send,
            edit,
            interval=0.2,
            sleep=sleep,
        )

        self.assertIs(result, message)
        self.assertEqual(events, [
            ("send", "ONE"),
            ("sleep", 0.2),
            ("edit", "ONE TWO"),
            ("sleep", 0.2),
            ("edit", "ONE TWO THREE"),
        ])

    async def test_activity_wraps_delay_and_progressive_send(self):
        events = []

        @asynccontextmanager
        async def activity(item):
            events.append(("activity_started", item.speaker))
            try:
                yield
            finally:
                events.append(("activity_finished", item.speaker))

        async def sleep(delay):
            events.append(("delay", delay))

        async def send(text):
            events.append(("ordinary_send", text))

        async def progressive_send(text):
            events.append(("progressive_send", text))

        await send_messages(
            [{"speaker": "zhenya", "text": "Печатаю", "delay": 1.5}],
            send,
            sleep=sleep,
            activity=activity,
            progressive_send=progressive_send,
        )

        self.assertEqual(events, [
            ("activity_started", "zhenya"),
            ("delay", 1.5),
            ("progressive_send", "Печатаю"),
            ("activity_finished", "zhenya"),
        ])

    def test_quest_uses_generic_message_delays(self):
        stages = (REPO_ROOT / "bot" / "quest" / "stages.yaml").read_text(encoding="utf-8")
        self.assertNotIn("argus_delay:", stages)
        self.assertNotIn("\n    argus:", stages)
        self.assertIn("messages:", stages)
        self.assertIn("speaker: argus", stages)
        self.assertIn("delay: 0.5", stages)

    def test_zhenya_replies_enable_typing_with_visible_delays(self):
        stages = (REPO_ROOT / "bot" / "quest" / "stages.yaml").read_text(encoding="utf-8")
        self.assertIn("welcome:\n  speaker: zhenya\n  delay: 1.5", stages)

        def stage_block(stage_id):
            remainder = stages.split(f"  {stage_id}:\n", 1)[1]
            return re.split(r"\n\n  (?=[A-Za-z0-9_]+:)", remainder, maxsplit=1)[0]

        z_1 = stage_block("z_1")
        self.assertEqual(z_1.count("speaker: zhenya"), 2)
        self.assertEqual(z_1.count("delay: 1.5"), 2)

        expected_stage_delays = {"z_2": "3", "z_3": "4", "z_4": "1.5"}
        for stage_id, delay in expected_stage_delays.items():
            block = stage_block(stage_id)
            self.assertIn(f"\n    speaker: zhenya\n    delay: {delay}", block)

        self.assertIn(
            "{speaker: zhenya, delay: 2.5, text: \"нет нет нет подож——\"}",
            stages,
        )

    def test_quest_unlock_waits_for_host_accept(self):
        stages = (REPO_ROOT / "bot" / "quest" / "stages.yaml").read_text(encoding="utf-8")
        block = stages.split("  quest_unlocked:\n", 1)[1].split("\n\n  ", 1)[0]
        self.assertIn("    mode: gate", block)
        self.assertIn("Мы свяжемся с тобой, когда придёт время", block)
        self.assertIn("    next: hub", block)

    async def test_stage_delay_waits_before_main_message(self):
        sleeps = []

        async def sleep(delay):
            sleeps.append(delay)

        await wait_before(0.75, sleep=sleep)
        await wait_before(0, sleep=sleep)
        self.assertEqual(sleeps, [0.75])


if __name__ == "__main__":
    unittest.main()
