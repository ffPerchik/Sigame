"""Валидация узла N6 «ТАЙНИК»: решётка Кардано → чужая раскладка → брайль → акростих.
Сверяет ассеты, константы генератора и accept-ответы в quest/stages.yaml."""
import ast
import sys
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.tools.quest_crypto import (
    BRAILLE_RU,
    braille_decode,
    braille_encode,
    wrong_layout_to_ru,
)

IMAGES = REPO_ROOT / "bot" / "quest" / "images"


def _load_quest() -> dict:
    return yaml.safe_load(
        (REPO_ROOT / "bot" / "quest" / "stages.yaml").read_text(encoding="utf-8")
    )


def _make_source_constants() -> dict:
    source = (REPO_ROOT / "bot" / "tools" / "make_quest_assets.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    wanted = {
        "N6_LETTER_LINES", "N6_GRILLE_HOLES", "N6_LAYOUT_CAPTION", "N6_NOTE_LINES",
    }
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in wanted for t in node.targets
        ):
            out[node.targets[0].id] = ast.literal_eval(node.value)
    assert wanted <= set(out), f"в генераторе не хватает констант: {wanted - set(out)}"
    return out


class N6ChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        quest = _load_quest()
        cls.stages = quest["stages"]
        cls.nodes = quest["nodes"]
        cls.consts = _make_source_constants()

    def test_grille_holes_spell_titry(self):
        lines = self.consts["N6_LETTER_LINES"]
        holes = [tuple(h) for h in self.consts["N6_GRILLE_HOLES"]]
        extract = "".join(lines[r][c] for r, c in sorted(holes))
        self.assertEqual(extract.upper(), "ТИТРЫ")
        self.assertIn("ТИТРЫ", self.stages["N6_grille"]["accept"])

    def test_layout_caption_decodes_to_tochki(self):
        caption = self.consts["N6_LAYOUT_CAPTION"]
        self.assertEqual(wrong_layout_to_ru(caption), "точки")
        self.assertIn("ТОЧКИ", self.stages["N6_layout"]["accept"])

    def test_braille_cells_spell_stroki(self):
        # контрольные клетки из опубликованной таблицы русского брайля
        self.assertEqual(BRAILLE_RU["т"], "2345")
        self.assertEqual(BRAILLE_RU["ы"], "2346")
        self.assertEqual(BRAILLE_RU["я"], "1246")
        cells = braille_encode("СТРОКИ")
        self.assertEqual(cells, ["234", "2345", "1235", "135", "13", "24"])
        self.assertEqual(braille_decode(cells), "строки")
        self.assertIn("СТРОКИ", self.stages["N6_braille"]["accept"])

    def test_note_acrostic_is_zhenya_zhiv(self):
        note = (IMAGES / "artifact_6f.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual("".join(line[0] for line in note), "ЖЕНЯЖИВ")
        self.assertEqual(note, self.consts["N6_NOTE_LINES"])
        self.assertIn("ЖЕНЯ ЖИВ", self.stages["N6_acrostic"]["accept"])

    def test_stage_chain_order_and_fragment(self):
        chain = [
            "N6_intro", "N6_grille", "N6_videoinfo", "N6_layout",
            "N6_brailleinfo", "N6_braille", "N6_noteinfo", "N6_acrostic",
            "N6_fragment",
        ]
        for current, nxt in zip(chain, chain[1:]):
            self.assertEqual(self.stages[current]["next"], nxt)
        self.assertEqual(self.stages["N6_fragment"]["next"], "hub")
        self.assertIn("ЗАВЕРШИ", self.stages["N6_fragment"]["text"])

    def test_four_media_delivered(self):
        st = self.stages
        self.assertEqual(st["N6_intro"]["image"], "artifact_6a.png")
        self.assertEqual(st["N6_intro"]["document"], "artifact_6b.png")
        self.assertEqual(st["N6_videoinfo"]["video"], "artifact_6c.mp4")
        self.assertEqual(st["N6_brailleinfo"]["document"], "artifact_6e.png")
        self.assertEqual(st["N6_noteinfo"]["document"], "artifact_6f.txt")
        for name in ("artifact_6a.png", "artifact_6b.png", "artifact_6c.mp4",
                     "artifact_6d.png", "artifact_6e.png", "artifact_6f.txt"):
            self.assertTrue((IMAGES / name).is_file(), name)

    def test_node_meta_consistent_with_texts(self):
        from bot import texts

        self.assertEqual(self.nodes["N6"]["label"], texts.NODE_LABELS["N6"])
        self.assertEqual(self.nodes["N6"]["hint"], texts.NODE_SHORT["N6"])


if __name__ == "__main__":
    unittest.main()
