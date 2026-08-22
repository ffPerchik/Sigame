import struct
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


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
        self.assertIn("start_y + index * 68", n3)
        self.assertIn("scale=25", n3)
        self.assertIn("width=7", n3)
        self.assertIn("parchment_page()", n3)
        self.assertIn("script_font(", n3)
        self.assertNotIn("hack_glitch", n3)
        self.assertNotIn("образец АБВ", n3)

    def test_reference_and_open_font_are_bundled(self):
        parchment = REPO_ROOT / "bot" / "quest" / "source" / "n3_parchment.png"
        script_font = REPO_ROOT / "bot" / "tools" / "fonts" / "MarckScript-Regular.ttf"
        license_file = REPO_ROOT / "bot" / "tools" / "fonts" / "OFL-MarckScript.txt"
        self.assertGreater(parchment.stat().st_size, 100_000)
        self.assertGreater(script_font.stat().st_size, 50_000)
        self.assertIn("SIL OPEN FONT LICENSE", license_file.read_text(encoding="utf-8").upper())


if __name__ == "__main__":
    unittest.main()
