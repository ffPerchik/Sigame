import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

# При прямом запуске файла Python добавляет в sys.path только bot/tools, а не
# корень репозитория. Добавляем его явно, чтобы одинаково работали оба варианта:
# `python bot/tools/test_sigame_achievements.py` и `python -m unittest ...`.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bot.tools.sigame_achievements as achievements
from bot.tools.sigame_achievements import (
    QuestionContext,
    calculate_awards,
    find_latest_log,
    load_package_questions,
    main,
    parse_html_log,
    parse_text_log,
    report_path_for,
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
        self.assertEqual(game.players["Bob"].wrong_count, 2)

        awards = calculate_awards(game)
        alice_codes = {award.code for award in awards["Alice"]}
        bob_codes = {award.code for award in awards["Bob"]}
        self.assertIn("champion", alice_codes)
        self.assertIn("almost_6767", alice_codes)
        self.assertIn("professor_minus", bob_codes)

    def test_sionline_text_log(self):
        content = """Theme A, 900
Player A: +100
Host изменил(а) сумму на счёте ⓈPlayer A с 100 на 450
Theme B, 200
Player B: -200
Game statistics:
ⓈPlayer A: Right: 4/1000, Wrong: 2/300
Player B: Right: 1/400, Wrong: 5/900
Game results
ⓈPlayer A: 700
Player B: -500
"""
        question_index = {
            ("Theme A", 900): QuestionContext("Round 1", "Theme A", 900),
            ("Theme B", 200): QuestionContext("Round 1", "Theme B", 200),
        }
        game = parse_text_log(Path("game.txt"), content, question_index)
        self.assertEqual(game.players["ⓈPlayer A"].right_count, 4)
        self.assertEqual(game.players["ⓈPlayer A"].final_score, 700)
        self.assertEqual(game.players["ⓈPlayer A"].right_by_theme, {"Theme A": 1})
        self.assertEqual(game.players["ⓈPlayer A"].manual_change_count, 1)
        self.assertEqual(game.players["ⓈPlayer A"].manual_total, 350)
        self.assertEqual(game.players["ⓈPlayer A"].net_by_round, {"Round 1": 450})
        self.assertEqual(len(game.outcomes), 3)
        self.assertEqual(game.outcomes[0].player, "ⓈPlayer A")
        self.assertEqual(game.outcomes[0].question_price, 900)
        self.assertEqual(game.outcomes[1].kind, "manual")
        self.assertEqual(game.outcomes[1].delta, 350)
        self.assertEqual(game.players["Player B"].wrong_count, 5)
        self.assertFalse(game.warnings)

        awards = calculate_awards(game)
        player_a_awards = {award.code: award for award in awards["ⓈPlayer A"]}
        self.assertIn("big_game_hunter", player_a_awards)
        self.assertIn("round_king_1", player_a_awards)
        self.assertIn("450 очков", player_a_awards["round_king_1"].evidence)

    def test_main_only_creates_txt_report(self):
        content = """🎬 Кинчик, 100
Alice: +100
Game results
Alice: 100
Game statistics:
Alice: Right: 1/100, Wrong: 0/0
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "game-log-test.txt"
            log_path.write_text(content, encoding="utf-8")

            stdout = io.StringIO()
            reports_dir = Path(temp_dir) / "quest" / "achievements"
            with patch.object(achievements, "REPORTS_DIR", reports_dir):
                with redirect_stdout(stdout):
                    self.assertEqual(main([str(log_path)]), 0)
                output_path = report_path_for(log_path)

            self.assertEqual(output_path.parent, reports_dir)
            self.assertTrue(output_path.exists())
            self.assertEqual(stdout.getvalue(), "")
            report = output_path.read_text(encoding="utf-8")
            self.assertIn("АЧИВКИ SIGAME", report)
            self.assertIn("Чемпион", report)
            self.assertIn("ИТОГО К НАЧИСЛЕНИЮ", report)
            self.assertIn("Alice —", report)
            self.assertNotIn("/addhint", report)

    def test_loads_question_context_from_package(self):
        index = load_package_questions(achievements.REPO_ROOT / "zengame.siq")
        context = index[("🎬 Кинчик", 100)]
        self.assertEqual(context.round_name, "Киномания")

    def test_refactored_paths_exist(self):
        self.assertEqual(achievements.BOT_ROOT, REPO_ROOT / "bot")
        self.assertEqual(
            achievements.REPORTS_DIR,
            REPO_ROOT / "bot" / "quest" / "achievements",
        )
        self.assertTrue((achievements.REPO_ROOT / "zengame.siq").is_file())
        self.assertTrue((REPO_ROOT / "bot" / "quest" / "source" / "n1_carrier.jpg").is_file())
        self.assertTrue((REPO_ROOT / "bot" / "tools" / "fonts" / "DejaVuSans.ttf").is_file())
        self.assertTrue((REPO_ROOT / "bot" / "docs" / "QUEST_WALKTHROUGH.md").is_file())

    def test_finds_latest_steam_log_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir) / "com.vladimirkhil.sigame" / "logs"
            logs_dir.mkdir(parents=True)
            steam_log = logs_dir / "game-log-2026-08-21.txt"
            steam_log.write_text("test", encoding="utf-8")
            (logs_dir / "game-log-2026-08-21-achievements.txt").write_text(
                "newer generated report",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"LOCALAPPDATA": temp_dir}):
                self.assertEqual(find_latest_log(None), steam_log)


if __name__ == "__main__":
    unittest.main()
