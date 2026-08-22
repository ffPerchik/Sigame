import ast
import math
import sys
import unittest
import wave
from array import array
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.tools.quest_crypto import RU_WITH_YO, vigenere


class N2AudioChainTests(unittest.TestCase):
    KEY = "КЛЮЧ"
    PLAIN = "СЛАБЫЙ ИМПУЛЬС ГАСНЕТ НО НОЧНОЙ ЭФИР ЕЩЕ АККУРАТНО ХРАНИТ ЕГО ПОД СЛОЕМ ЛЬДА"
    CIPHER = "ЬЧЮШЁХ ЖДЪЯЙУЬ ОЮИШРР ЕЩ ЩМОШЪЗ ФЯФО ЬДР ЮВХЯОЧЭЩМ МЫЛЛАЭ РБЁ ЪЪВ ИЦЪГД ЦЗВЧ"

    @staticmethod
    def _read_wav(name):
        path = REPO_ROOT / "bot" / "quest" / "images" / name
        with wave.open(str(path), "rb") as wav:
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            rate = wav.getframerate()
            frames = wav.getnframes()
            samples = array("h", wav.readframes(frames))
        if sys.byteorder != "little":
            samples.byteswap()
        return channels, width, rate, frames, samples

    def test_vigenere_and_fibonacci_layers_produce_final_answer(self):
        self.assertEqual(
            vigenere(self.PLAIN, self.KEY, alphabet=RU_WITH_YO),
            self.CIPHER,
        )
        self.assertEqual(
            vigenere(self.CIPHER, self.KEY, decrypt=True, alphabet=RU_WITH_YO),
            self.PLAIN,
        )
        self.assertEqual(
            vigenere("ЬЧЮШЁХ ЖДЪЯЙУЬ", "ключ", decrypt=True, alphabet=RU_WITH_YO),
            "СЛАБЫЙ ИМПУЛЬС",
        )
        words = self.PLAIN.split()
        answer = "".join(words[index - 1][0] for index in (1, 2, 3, 5, 8, 13))
        self.assertEqual(answer, "СИГНАЛ")

    def test_quest_uses_single_connected_audio_chain(self):
        stages = (REPO_ROOT / "bot" / "quest" / "stages.yaml").read_text(encoding="utf-8")
        for filename in ("n2_1.wav", "n2_2.wav", "n2_3.wav"):
            self.assertIn(filename, stages)
            self.assertTrue((REPO_ROOT / "bot" / "quest" / "images" / filename).is_file())
        self.assertIn('      - "СИГНАЛ"', stages)
        self.assertNotIn("n2_spec.wav", stages)

    def test_phone_tones_encode_fibonacci_digits(self):
        channels, width, rate, _frames, samples = self._read_wav("n2_2.wav")
        self.assertEqual((channels, width, rate), (1, 2, 22050))

        frame_size = rate // 100  # 10 ms
        threshold_squared = 2500 ** 2
        active = []
        for start in range(0, len(samples) - frame_size + 1, frame_size):
            block = samples[start:start + frame_size]
            active.append(sum(value * value for value in block) / frame_size > threshold_squared)

        tone_ranges = []
        start = None
        for index, is_tone in enumerate(active + [False]):
            if is_tone and start is None:
                start = index
            elif not is_tone and start is not None:
                tone_ranges.append((start * frame_size, index * frame_size))
                start = None
        self.assertEqual(len(tone_ranges), 6)

        def goertzel_power(values, frequency):
            coefficient = 2 * math.cos(2 * math.pi * frequency / rate)
            previous = previous2 = 0.0
            for value in values:
                current = value + coefficient * previous - previous2
                previous2, previous = previous, current
            return previous2 ** 2 + previous ** 2 - coefficient * previous * previous2

        rows = (697, 770, 852, 941)
        columns = (1209, 1336, 1477)
        keypad = {
            (697, 1209): "1", (697, 1336): "2", (697, 1477): "3",
            (770, 1209): "4", (770, 1336): "5", (770, 1477): "6",
            (852, 1209): "7", (852, 1336): "8", (852, 1477): "9",
            (941, 1336): "0",
        }
        decoded = []
        for first, last in tone_ranges:
            values = samples[first:last]
            row = max(rows, key=lambda frequency: goertzel_power(values, frequency))
            column = max(columns, key=lambda frequency: goertzel_power(values, frequency))
            decoded.append(keypad[(row, column)])
        self.assertEqual("".join(decoded), "112358")

    def test_cipher_is_short_multiline_spectrogram(self):
        channels, width, rate, frames, _samples = self._read_wav("n2_3.wav")
        self.assertEqual((channels, width, rate), (1, 2, 22050))
        self.assertGreater(frames / rate, 8.0)
        self.assertLess(frames / rate, 15.0)

        source = (REPO_ROOT / "bot" / "tools" / "make_quest_assets.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        lines = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "N2_SPECTROGRAM_LINES"
                for target in node.targets
            )
        )
        self.assertEqual(lines[0], "ВИЖЕНЕР")
        self.assertEqual(" ".join(lines[1:]), self.CIPHER)
        pixel_font = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "PIXEL_FONT_5x7"
        )
        self.assertEqual(pixel_font["Д"][-1], "10001")
        self.assertEqual(pixel_font["Ц"][-1], "00001")
        self.assertIn("make_ballet_waltz(total_samples, sr)", source)
        self.assertIn("music * 0.92 + hidden * 0.08", source)


if __name__ == "__main__":
    unittest.main()
