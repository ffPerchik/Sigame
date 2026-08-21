import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sigame_achievements import (
    calculate_awards,
    find_latest_log,
    parse_html_log,
    parse_text_log,
)


class SIGameAchievementsTests(unittest.TestCase):
    def test_desktop_html_log(self):
        parts = [
            '<span data-tag="gameInfo" data-showman="Host" '
            'data-player-0="Alice" data-player-1="Bob"></span>'
        ]
        # Alice набирает 6700, в том числе отвечает «67».
        for i, delta in enumerate([1000, 1000, 1000, 1000, 1000, 1000, 700]):
            answer = "67" if i == 0 else f"a{i}"
            parts.append(f'<span class="sr n0">Alice: </span><span class="r">{answer}</span><br/>')
            parts.append(f'<span data-tag="sumChange" data-playerIndex="0" data-change="{delta}"></span>')
        # Bob дважды ошибается, второй ответ длиннее.
        for answer, delta in [("x", -100), ("очень длинный неверный ответ", -200)]:
            parts.append(f'<span class="sr n1">Bob: </span><span class="r">{answer}</span><br/>')
            parts.append(f'<span data-tag="sumChange" data-playerIndex="1" data-change="{delta}"></span>')

        game = parse_html_log(Path("game.html"), "".join(parts))
        self.assertEqual(game.players["Alice"].final_score, 6700)
        self.assertEqual(game.players["Alice"].right_count, 7)
        self.assertEqual(game.players["Alice"].answer_67_count, 1)
        self.assertEqual(game.players["Bob"].wrong_count, 2)

        awards = calculate_awards(game)
        alice_codes = {award.code for award in awards["Alice"]}
        bob_codes = {award.code for award in awards["Bob"]}
        self.assertIn("champion", alice_codes)
        self.assertIn("almost_6767", alice_codes)
        self.assertIn("area_67", alice_codes)
        self.assertIn("professor_minus", bob_codes)
        self.assertIn("longread", bob_codes)

    def test_sionline_text_log(self):
        content = """Player A: +100
Player B: -200
Game statistics:
Player A: Right: 4/1000, Wrong: 2/300
Player B: Right: 1/400, Wrong: 5/900
Game results
Player A: 700
Player B: -500
"""
        game = parse_text_log(Path("game.txt"), content)
        self.assertEqual(game.players["Player A"].right_count, 4)
        self.assertEqual(game.players["Player A"].final_score, 700)
        self.assertEqual(game.players["Player B"].wrong_count, 5)
        self.assertTrue(any("PLAYER_ANSWER" in warning for warning in game.warnings))

    def test_finds_latest_steam_log_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir) / "com.vladimirkhil.sigame" / "logs"
            logs_dir.mkdir(parents=True)
            steam_log = logs_dir / "game-log-2026-08-21.txt"
            steam_log.write_text("test", encoding="utf-8")

            with patch.dict(os.environ, {"LOCALAPPDATA": temp_dir}):
                self.assertEqual(find_latest_log(None), steam_log)


if __name__ == "__main__":
    unittest.main()
