import ast
import sys
import unittest
import wave
from array import array
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.tools.quest_crypto import vigenere


class N2AudioChainTests(unittest.TestCase):
    KEY = "КЛЮЧ"
    PLAIN = "СЛАБЫЙ ИМПУЛЬС ГАСНЕТ НО НОЧНОЙ ЭФИР ЕЩЕ АККУРАТНО ХРАНИТ ЕГО ПОД СЛОЕМ ЛЬДА"
    CIPHER = "ЫЦЮШЕФ ЖГЩЮЙУЫ ОЮИЧРР ДШ ШМОЧЩЗ ФЮУО ЬГР ЮБФЮОЧЬШМ МЪЛЛЯЬ РБЕ ЩЩВ ИХЩГГ ХЗВЧ"

    def test_vigenere_and_fibonacci_layers_produce_final_answer(self):
        self.assertEqual(vigenere(self.PLAIN, self.KEY), self.CIPHER)
        self.assertEqual(vigenere(self.CIPHER, self.KEY, decrypt=True), self.PLAIN)
        words = self.PLAIN.split()
        answer = "".join(words[index - 1][0] for index in (1, 2, 3, 5, 8, 13))
        self.assertEqual(answer, "СИГНАЛ")

    def test_quest_uses_single_connected_audio_chain(self):
        stages = (REPO_ROOT / "bot" / "quest" / "stages.yaml").read_text(encoding="utf-8")
        for filename in ("n2_reversed.wav", "n2_spec.wav", "n2_cipher.wav"):
            self.assertIn(filename, stages)
            self.assertTrue((REPO_ROOT / "bot" / "quest" / "images" / filename).is_file())
        self.assertIn('      - "ЛЬДА"', stages)
        self.assertIn('      - "СИГНАЛ"', stages)
        self.assertNotIn("n2_verse.png", stages)

    def test_cipher_audio_round_trips_through_morse(self):
        path = REPO_ROOT / "bot" / "quest" / "images" / "n2_cipher.wav"
        with wave.open(str(path), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            sample_rate = wav.getframerate()
            self.assertEqual(sample_rate, 22050)
            self.assertGreater(wav.getnframes() / sample_rate, 30.0)
            samples = array("h", wav.readframes(wav.getnframes()))
        if sys.byteorder != "little":
            samples.byteswap()

        unit = int(sample_rate * 0.045)
        active = []
        threshold_squared = 4000 ** 2
        for start in range(0, len(samples) - unit + 1, unit):
            block = samples[start:start + unit]
            active.append(sum(value * value for value in block) / unit > threshold_squared)

        runs = []
        current = active[0]
        length = 0
        for value in active:
            if value == current:
                length += 1
            else:
                runs.append((current, length))
                current, length = value, 1
        runs.append((current, length))

        source = (REPO_ROOT / "bot" / "tools" / "make_quest_assets.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        morse = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "MORSE_RU" for target in node.targets)
        )
        decode = {code: letter for letter, code in morse.items()}
        words, letters, code = [], [], ""
        for is_tone, run_length in runs:
            if is_tone:
                code += "." if run_length <= 1 else "-"
            elif run_length >= 8:
                if code:
                    letters.append(decode[code])
                    code = ""
                words.append("".join(letters))
                letters = []
            elif run_length >= 3 and code:
                letters.append(decode[code])
                code = ""
        if code:
            letters.append(decode[code])
        if letters:
            words.append("".join(letters))

        self.assertEqual(" ".join(words), f"ВИЖЕНЕР {self.CIPHER}")


if __name__ == "__main__":
    unittest.main()
