import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.media_spec import MediaSpec, delivery_field, parse_media_spec


class MediaSpecTests(unittest.TestCase):
    def test_document_without_flag_stays_uncompressed(self):
        spec = parse_media_spec("n1_card.jpg")
        self.assertEqual(spec, MediaSpec("n1_card.jpg", False))
        self.assertEqual(delivery_field("document", spec), "document")

    def test_latin_compress_flag_turns_document_into_photo(self):
        spec = parse_media_spec("z_3.png -c")
        self.assertEqual(spec, MediaSpec("z_3.png", True))
        self.assertEqual(delivery_field("document", spec), "image")

    def test_cyrillic_and_long_flags_are_supported(self):
        for value in ("картинка с пробелами.png -с", "картинка с пробелами.png --compress"):
            spec = parse_media_spec(value)
            self.assertEqual(spec.path, "картинка с пробелами.png")
            self.assertTrue(spec.compress)
            self.assertEqual(delivery_field("document", spec), "image")

    def test_compress_rejects_non_image_document(self):
        with self.assertRaises(ValueError):
            delivery_field("document", parse_media_spec("archive.zip -c"))

    def test_image_field_is_already_compressed(self):
        self.assertEqual(delivery_field("image", parse_media_spec("photo.png -c")), "image")


if __name__ == "__main__":
    unittest.main()
