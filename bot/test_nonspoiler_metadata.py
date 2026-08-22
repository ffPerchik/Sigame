import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class NonSpoilerMetadataTests(unittest.TestCase):
    ARTIFACTS = (
        "n2_1.wav", "n2_2.wav", "n2_3.wav",
        "artifact_3a.png", "artifact_3b.png", "artifact_3c.png", "artifact_3d.png",
        "artifact_4a.mp4", "artifact_4b.png", "artifact_4c.png",
        "artifact_5a.png", "artifact_5b.html", "artifact_5c.png",
        "artifact_6a.png",
    )
    OLD_NAMES = (
        "n2_reversed.wav", "n2_fibo.wav", "n2_cipher.wav",
        "n3_pigpen.png", "n3_rail.png", "n3_vig.png", "n3_book.png",
        "n4_walk.mp4", "n4_signs.png", "n4_shards.png",
        "n5_table.png", "n5_ledger.html", "n5_lock.png", "n6_locks.png",
    )

    def test_hub_descriptions_do_not_name_solution_methods(self):
        stages = (REPO_ROOT / "bot" / "quest" / "stages.yaml").read_text(encoding="utf-8")
        node_lines = "\n".join(
            line for line in stages.splitlines()
            if line.startswith(("  N3:", "  N4:", "  N5:", "  N6:"))
        ).lower()
        for spoiler in (
            "пигпен", "зигзаг", "виженер", "книга", "вывески", "вспышка",
            "биты", "квадрат", "html", "замок", "зеркало", "рельсы", "a1z26",
        ):
            self.assertNotIn(spoiler, node_lines)
        for category in ("бумажные шифры", "видео", "числовая логика", "цепочка шифров"):
            self.assertIn(category, node_lines)

    def test_task_texts_hint_without_naming_the_method(self):
        stages = (REPO_ROOT / "bot" / "quest" / "stages.yaml").read_text(encoding="utf-8")
        lines = stages.splitlines()
        task_texts = []
        current_stage = ""
        index = 0
        while index < len(lines):
            line = lines[index]
            if line.startswith("  N") and not line.startswith("    ") and line.endswith(":"):
                current_stage = line.strip()[:-1]
            if current_stage.startswith(("N3_", "N4_", "N5_", "N6_")) and line == "    text: |":
                block = []
                index += 1
                while index < len(lines) and (not lines[index].strip() or lines[index].startswith("      ")):
                    block.append(lines[index].strip())
                    index += 1
                task_texts.append(" ".join(block).lower())
                continue
            index += 1

        combined = "\n".join(task_texts)
        for direct_instruction in (
            "ключ у тебя", "зигзаг", "рельс", "виженер", "a1z26", "utf-8",
            "вычитай", "декодируй", "пиши", "разложи", "первые пять по порядку",
        ):
            self.assertNotIn(direct_instruction, combined)
        self.assertIn("первое слово всё ещё с тобой", combined)
        self.assertIn("алфавит только с одной стороны", combined)

    def test_player_facing_assets_have_neutral_names(self):
        images = REPO_ROOT / "bot" / "quest" / "images"
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                REPO_ROOT / "bot" / "quest" / "stages.yaml",
                REPO_ROOT / "bot" / "tools" / "make_quest_assets.py",
                REPO_ROOT / "bot" / "docs" / "QUEST_WALKTHROUGH.md",
            )
        )
        for filename in self.ARTIFACTS:
            self.assertTrue((images / filename).is_file(), filename)
            self.assertIn(filename, combined)
        for filename in self.OLD_NAMES:
            self.assertFalse((images / filename).exists(), filename)
            self.assertNotIn(filename, combined)


if __name__ == "__main__":
    unittest.main()
