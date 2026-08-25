import struct
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.tools.quest_crypto import rail_fence_dec, rail_fence_enc


class N3CardStyleTests(unittest.TestCase):
    def test_cards_are_portrait_parchment_pages(self):
        images = REPO_ROOT / "bot" / "quest" / "images"
        for name in ("artifact_3a.png", "artifact_3b.png", "artifact_3c.png", "artifact_3d.png"):
            raw = (images / name).read_bytes()
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            width, height = struct.unpack(">II", raw[16:24])
            self.assertEqual((width, height), (1024, 1536))

    def test_generator_uses_script_font_without_glitches(self):
        source = (REPO_ROOT / "bot" / "tools" / "make_quest_assets.py").read_text(encoding="utf-8")
        n3 = source.split("def make_n3():", 1)[1].split("# ===================================================================== N4", 1)[0]
        self.assertIn('crib = "СИКССЕВЕН"', n3)
        self.assertIn('"Решил создать новый язык,"', n3)
        self.assertIn('"«сикс севен»"', n3)
        self.assertIn("scale=11, color=ink, width=5", n3)
        self.assertIn('Image.new("RGBA", (610, 105)', n3)
        self.assertIn("message_strip.rotate(", n3)
        self.assertIn("-45,", n3)
        self.assertIn("scale=23", n3)
        self.assertIn("width=7", n3)
        self.assertIn("draw_pigpen_diamond_key", n3)
        self.assertIn('letters="ТУФХЦЧШЩЪ"', source)
        self.assertIn("draw_pigpen_square_key", n3)
        self.assertIn('letters="АБВГДЕЖЗИ"', source)
        diamond_key = source.split("def draw_pigpen_diamond_key", 1)[1].split("def draw_pigpen_square_key", 1)[0]
        square_key = source.split("def draw_pigpen_square_key", 1)[1].split("def burn_lower_left_corner", 1)[0]
        self.assertIn("for offset in (-cell / 2, cell / 2):", diamond_key)
        self.assertIn("for offset in (-cell / 2, cell / 2):", square_key)
        self.assertNotIn("range(4)", diamond_key)
        self.assertNotIn("range(4)", square_key)
        self.assertIn("burn_lower_left_corner(page1)", n3)
        self.assertNotIn("А теперь — загадка", n3)
        self.assertIn("parchment_page()", n3)
        self.assertIn("parchment_page(PARCHMENT_SOURCE_2)", n3)
        self.assertIn("parchment_page(PARCHMENT_SOURCE_3)", n3)
        self.assertIn("parchment_page(PARCHMENT_SOURCE_4)", n3)
        self.assertIn("script_font(", n3)
        self.assertNotIn("hack_glitch", n3)
        self.assertNotIn("образец АБВ", n3)

    def test_diamond_family_keeps_all_nine_positions_distinct(self):
        source = (REPO_ROOT / "bot" / "tools" / "make_quest_assets.py").read_text(encoding="utf-8")
        pigpen = source.split("def draw_pigpen(", 1)[1].split("def draw_pigpen_diamond_key", 1)[0]
        self.assertIn('if kind == "x":', pigpen)
        self.assertIn("rotate_point", pigpen)
        self.assertNotIn("pos % 4", pigpen)

    def test_second_sheet_hides_the_answer_in_a_full_sentence(self):
        plain = "СЛЕДУЮЩИЙШИФРНОСИТИМЯПОЛИБИЯ"
        cipher = rail_fence_enc(plain, 3)
        self.assertEqual(cipher, "СУЙРИЯИЛДЮИШФНСТМПЛБЯЕЩИОИОИ")
        self.assertNotIn("ПОЛИБИЙ", cipher)
        self.assertEqual(rail_fence_dec(cipher, 3), plain)

        source = (REPO_ROOT / "bot" / "tools" / "make_quest_assets.py").read_text(encoding="utf-8")
        n3 = source.split("def make_n3():", 1)[1].split("# ===================================================================== N4", 1)[0]
        self.assertIn(f'rail_plain = "{plain}"', n3)
        self.assertIn("assert rail_counts == [7, 14, 7]", n3)
        self.assertIn('polybius_pairs == ["43", "14", "11", "41", "45", "16"]', n3)
        self.assertIn('margin_text = "«первое слово начинает алфавит»"', n3)
        self.assertNotIn('margin_text = "на полях:', n3)
        self.assertIn("margin_layer.rotate(90", n3)
        self.assertIn('{(2, 5): "Ё", (6, 3): "Я"}', n3)
        self.assertNotIn("33 буквы, включая ё", n3)
        self.assertNotIn("сначала строка, потом столбец", n3)
        self.assertNotIn("vigenere(", n3)
        self.assertNotIn("ВИЖНЕР", n3)

    def test_final_sheet_uses_all_three_previous_answers(self):
        source = (REPO_ROOT / "bot" / "tools" / "make_quest_assets.py").read_text(encoding="utf-8")
        n3 = source.split("def make_n3():", 1)[1].split("# ===================================================================== N4", 1)[0]
        self.assertIn('header_key = "ФАСОТР"', n3)
        self.assertIn("sorted(header_key) == sorted(keyword)", n3)
        self.assertIn("sort_order == [3, 5, 6, 4, 1, 2]", n3)
        self.assertIn('answer4 = "ИСТИНА"', n3)
        self.assertIn("sort_order.index(row) + 1", n3)
        self.assertIn('[(4, 3), (5, 4), (5, 1), (4, 1), (4, 5), (5, 6)]', n3)
        self.assertIn("верхний ряд сбился с порядка", n3)
        self.assertIn("третье слово знает, как его вернуть", n3)
        self.assertIn("язык первого листа ещё нужен", n3)
        self.assertIn("draw_pigpen(", n3.split("page4 = parchment_page")[1])
        self.assertNotIn('unique_key == "РЕШТКА"', n3)
        self.assertNotIn("столбцы помнят первое слово", n3)
        self.assertNotIn("Тихий ветер гасит свет пряча архив", n3)

    def test_reference_and_open_font_are_bundled(self):
        source_dir = REPO_ROOT / "bot" / "quest" / "source"
        parchments = [source_dir / name for name in (
            "n3_parchment.png", "n3_parchment_2.png", "n3_parchment_3.png",
            "n3_parchment_4.png",
        )]
        for parchment in parchments:
            raw = parchment.read_bytes()
            self.assertGreater(len(raw), 100_000)
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", raw[16:24]), (848, 1264))
        self.assertEqual(len({parchment.read_bytes() for parchment in parchments}), 4)

        script_font = REPO_ROOT / "bot" / "tools" / "fonts" / "MarckScript-Regular.ttf"
        license_file = REPO_ROOT / "bot" / "tools" / "fonts" / "OFL-MarckScript.txt"
        self.assertGreater(script_font.stat().st_size, 50_000)
        self.assertIn("SIL OPEN FONT LICENSE", license_file.read_text(encoding="utf-8").upper())


if __name__ == "__main__":
    unittest.main()
