import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot import reloader


class ReloaderTests(unittest.TestCase):
    def test_python_tree_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "good.py").write_text("value = 42\n", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            (nested / "also_good.py").write_text("def f():\n    return 1\n", encoding="utf-8")

            ok, details = reloader.validate_python_tree(root)
            self.assertTrue(ok)
            self.assertIn("2", details)

            (nested / "broken.py").write_text("def broken(:\n", encoding="utf-8")
            ok, error = reloader.validate_python_tree(root)
            self.assertFalse(ok)
            self.assertIn("nested", error)
            self.assertIn("broken.py", error)
            self.assertIn("SyntaxError", error)

    def test_restart_keeps_process_arguments(self):
        with patch.object(reloader.os, "execv") as execv:
            with self.assertRaises(RuntimeError):
                reloader.restart_current_process(
                    argv=["bot.py", "--flag"],
                    executable="python-test",
                )
        execv.assert_called_once_with(
            "python-test", ["python-test", "bot.py", "--flag"]
        )


if __name__ == "__main__":
    unittest.main()
