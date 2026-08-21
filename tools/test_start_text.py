import base64
import re
import sys
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.build_v5 import quest_start_text


class StartTextTests(unittest.TestCase):
    def test_package_contains_current_start_text(self):
        with zipfile.ZipFile(REPO_ROOT / "zengame.siq") as package:
            self.assertEqual(package.read("START.txt").decode("utf-8"), quest_start_text())

    def test_start_text_sends_to_bot_and_preserves_activation_key(self):
        text = quest_start_text()
        encoded_lines = [
            line.strip()
            for line in text.splitlines()
            if re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", line.strip())
        ]
        # Первый блок переносится по 64 символа, последний короткий блок — ключ.
        key = base64.b64decode(encoded_lines[-1]).decode("utf-8")
        greeting = base64.b64decode("".join(encoded_lines[:-1])).decode("utf-8")
        self.assertEqual(key, "ARGUS1001")
        stages_text = (REPO_ROOT / "bot" / "quest" / "stages.yaml").read_text(encoding="utf-8")
        configured_key = re.search(r'^entry_code:\s*["\']?([^"\'\s]+)', stages_text, re.MULTILINE)
        self.assertIsNotNone(configured_key)
        self.assertEqual(key, configured_key.group(1))
        self.assertIn("@Zengame_checker_bot", greeting)
        self.assertIn("ОБЫЧНЫЙ START", greeting)
        self.assertIn("СОХРАНИ ЕГО", greeting)
        self.assertIn("ПОСЛЕ ПРОЛОГА ARGVS ПОТРЕБУЕТ КЛЮЧ", greeting)


if __name__ == "__main__":
    unittest.main()
