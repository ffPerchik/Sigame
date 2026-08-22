import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class NonSpoilerMetadataTests(unittest.TestCase):
    ARTIFACTS = (
        "artifact_3a.png", "artifact_3b.png", "artifact_3c.png", "artifact_3d.png",
        "artifact_4a.mp4", "artifact_4b.png", "artifact_4c.png",
        "artifact_5a.png", "artifact_5b.html", "artifact_5c.png",
        "artifact_6a.png",
    )
    OLD_NAMES = (
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
