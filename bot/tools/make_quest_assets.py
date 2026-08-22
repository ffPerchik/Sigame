#!/usr/bin/env python3
"""Генератор медиа для ARG «Аргус-1001» (6 независимых узлов, много слоёв)."""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np
import piexif
from PIL import Image, ImageDraw, ImageFont

try:
    from .quest_crypto import (
        RU, RU_WITH_YO, a1z26_encode, atbash, only_ru, pigpen_cell,
        rail_fence_enc, vigenere,
    )
except ImportError:  # запуск как `python bot/tools/make_quest_assets.py`
    from quest_crypto import (
        RU, RU_WITH_YO, a1z26_encode, atbash, only_ru, pigpen_cell,
        rail_fence_enc, vigenere,
    )

BOT_ROOT = Path(__file__).resolve().parent.parent
OUT = BOT_ROOT / "quest" / "images"
OUT.mkdir(parents=True, exist_ok=True)

FONTS = [
    str(BOT_ROOT / "tools" / "fonts" / "DejaVuSans-Bold.ttf"),
    str(BOT_ROOT / "tools" / "fonts" / "DejaVuSans.ttf"),
    str(BOT_ROOT / "tools" / "fonts" / "DejaVuSansMono-Bold.ttf"),
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in FONTS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    raise FileNotFoundError(
        "Нет шрифта с кириллицей. В репо должен быть bot/tools/fonts/DejaVuSans-Bold.ttf"
    )



def hack_glitch(
    img: Image.Image,
    seed: int = 1,
    keep_rect: tuple[int, int, int, int] | None = None,
    power: float = 1.0,
    scanlines: bool = False,
) -> Image.Image:
    """Лёгкий «взлом»: сдвиг канала, битые пиксели по краям.
    keep_rect = (x0,y0,x1,y1) не трогаем (текст на мониторе и т.п.)."""
    arr = np.array(img.convert("RGB"), dtype=np.int16)
    h, w = arr.shape[:2]
    rng = np.random.default_rng(seed)
    power = max(0.0, power)

    def _ok(x, y):
        if keep_rect is None:
            return True
        x0, y0, x1, y1 = keep_rect
        return not (x0 <= x <= x1 and y0 <= y <= y1)

    if scanlines:
        arr[::7, :, :] = np.clip(
            arr[::7] + rng.integers(-10, 16) * power,
            0,
            255,
        )

    sh = max(1, int(round(2 * power)))
    if sh < w:
        arr[:, sh:, 0] = arr[:, :-sh, 0]
        arr[:, :-sh, 2] = arr[:, sh:, 2]

    for _ in range(max(1, int(max(18, w * h // 1000) * power))):
        x = int(rng.integers(0, max(w - 8, 1)))
        y = int(rng.integers(0, max(h - 6, 1)))

        if not _ok(x, y):
            continue

        bw = max(1, int(rng.integers(2, 9) * power))
        bh = max(1, int(rng.integers(1, 5) * power))
        val = int(rng.choice([0, 255, 30, 210, 0, 40]))
        ch = int(rng.integers(0, 3))

        x1 = min(w, x + bw)
        y1 = min(h, y + bh)

        if keep_rect is not None:
            x0, y0, rx1, ry1 = keep_rect
            if not (x1 < x0 or x > rx1 or y1 < y0 or y > ry1):
                continue

        arr[y:y1, x:x1, ch] = val

    for _ in range(max(1, int(max(8, w * h // 6000) * power))):
        x = int(rng.integers(0, max(w - 4, 1)))
        y = int(rng.integers(0, max(h - 3, 1)))

        if not _ok(x, y):
            continue

        bw = max(
            1,
            int(
                rng.integers(4, max(5, min(30, w // 8 + 1)))
                * power
            ),
        )
        bh = max(
            1,
            int(
                rng.integers(3, max(4, min(20, h // 8 + 1)))
                * power
            ),
        )

        x1 = min(w, x + bw)
        y1 = min(h, y + bh)

        if keep_rect is not None:
            x0, y0, rx1, ry1 = keep_rect
            if not (x1 < x0 or x > rx1 or y1 < y0 or y > ry1):
                continue

        arr[y:y1, x:x1, :] = 0

    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


# ===================================================================== N1
def draw_pigpen(draw: ImageDraw.ImageDraw, xy: tuple[int, int], ch: str, scale=18):
    idx = RU.index(ch)
    kind, dotted, pos = pigpen_cell(idx)
    x, y = xy
    s = scale
    # 3×3 позиции: 0 1 2 / 3 4 5 / 6 7 8
    r, c = divmod(pos, 3)
    # стенки «коробки»: рисуем отсутствующие внешние? классика — рисуем линии клетки
    # упрощённо: квадрат с пропущенной стороной к центру группы
    cx, cy = x + s, y + s
    if kind == "box":
        # внешние линии в зависимости от позиции
        # top
        if r != 0:
            draw.line((x, y, x + 2 * s, y), fill=(20, 20, 20), width=3)
        # bottom
        if r != 2:
            draw.line((x, y + 2 * s, x + 2 * s, y + 2 * s), fill=(20, 20, 20), width=3)
        # left
        if c != 0:
            draw.line((x, y, x, y + 2 * s), fill=(20, 20, 20), width=3)
        # right
        if c != 2:
            draw.line((x + 2 * s, y, x + 2 * s, y + 2 * s), fill=(20, 20, 20), width=3)
    else:
        # X-семейство: два луча, ориентация по pos 0..3 обычно, у нас 0..8
        arms = [
            [(cx, cy, cx, y), (cx, cy, x + 2 * s, cy)],  # up-right
            [(cx, cy, x + 2 * s, cy), (cx, cy, cx, y + 2 * s)],
            [(cx, cy, cx, y + 2 * s), (cx, cy, x, cy)],
            [(cx, cy, x, cy), (cx, cy, cx, y)],
        ]
        pair = arms[pos % 4]
        for seg in pair:
            draw.line(seg, fill=(20, 20, 20), width=3)
    if dotted:
        draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=(20, 20, 20))


def _n1_still() -> Image.Image:
    """Свой кадр для N1 — bot/quest/source/n1_carrier.jpg, не финал SIGame."""
    src = BOT_ROOT / "quest" / "source" / "n1_carrier.jpg"
    img = Image.open(src).convert("RGB")
    return img.resize((1200, 800))


def make_n1():
    """Скрытая надпись на кадре (делает ведущий на n1_carrier) → EXIF FFD9 → хвост JPEG → A1Z26 СЛОИ.

    LSB/каналы не используем: вход из SIGame уже LSB, онлайн-декодеры наш LSB не видели.
    Хвост после FFD9 живёт, только если бот шлёт JPEG как document.
    """
    img = hack_glitch(_n1_still(), seed=1001, keep_rect=(780, 250, 1180, 560))
    msg = a1z26_encode("СЛОИ")
    jpg_path = OUT / "n1_card.jpg"
    import piexif.helper
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Artist: "255,217",
        },
        "Exif": {
            piexif.ExifIFD.UserComment: piexif.helper.UserComment.dump(
                'Ищи "secret code" в битах',
                encoding="unicode",
            ),
        },
    }
    img.save(jpg_path, "JPEG", quality=92, exif=piexif.dump(exif_dict))
    tail = b"\nsecret code: " + msg.encode("ascii") + b"\n"
    with jpg_path.open("ab") as f:
        f.write(tail)
    raw = jpg_path.read_bytes()
    assert raw[-len(tail):] == tail
    print("  N1  надпись на кадре рисует ведущий на bot/quest/source/n1_carrier.jpg → СМОТРИ ВНУТРЬ")
    print("  N1  EXIF Artist=255,217 (= FF D9), без текстового спойлера")
    print(f"  N1  после FFD9 дописано «secret code: {msg}» → СЛОИ")
    return jpg_path


# ===================================================================== N2
PIXEL_FONT_5x7: dict[str, list[str]] = {
    "А": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "Б": ["11111", "10000", "10000", "11110", "10001", "10001", "11110"],
    "В": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "Г": ["11111", "10000", "10000", "10000", "10000", "10000", "10000"],
    "Д": ["01110", "01010", "01010", "01010", "01010", "11111", "10001"],
    "Е": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "Ё": ["01010", "11111", "10000", "11110", "10000", "10000", "11111"],
    "Ж": ["10001", "10101", "01010", "00100", "01010", "10101", "10001"],
    "З": ["01110", "10001", "00001", "00110", "00001", "10001", "01110"],
    "И": ["10001", "10001", "10011", "10101", "11001", "10001", "10001"],
    "Й": ["00100", "10001", "10011", "10101", "11001", "10001", "10001"],
    "К": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "Л": ["00111", "01001", "01001", "01001", "01001", "01001", "10001"],
    "М": ["10001", "11011", "10101", "10001", "10001", "10001", "10001"],
    "Н": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "О": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "П": ["11111", "10001", "10001", "10001", "10001", "10001", "10001"],
    "Р": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "С": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "Т": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "У": ["10001", "10001", "10001", "01010", "00100", "00100", "01100"],
    "Ф": ["00100", "01110", "10101", "10101", "01110", "00100", "00100"],
    "Х": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Ц": ["10010", "10010", "10010", "10010", "10010", "11111", "00001"],
    "Ч": ["10001", "10001", "10001", "01111", "00001", "00001", "00001"],
    "Ш": ["10001", "10001", "10001", "10101", "10101", "10101", "11111"],
    "Щ": ["10001", "10001", "10001", "10101", "10101", "11111", "00001"],
    "Ъ": ["11000", "01000", "01110", "01001", "01001", "01001", "01110"],
    "Ы": ["10001", "10001", "10001", "11101", "10011", "10011", "11101"],
    "Ь": ["10000", "10000", "11110", "10001", "10001", "10001", "11110"],
    "Э": ["01110", "10001", "00001", "00111", "00001", "10001", "01110"],
    "Ю": ["10010", "10101", "10101", "11101", "10101", "10101", "10010"],
    "Я": ["01111", "10001", "10001", "01111", "00101", "01001", "10001"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}

# русская азбука Морзе
MORSE_RU = {
    "А": ".-", "Б": "-...", "В": ".--", "Г": "--.", "Д": "-..", "Е": ".",
    "Ж": "...-", "З": "--..", "И": "..", "Й": ".---", "К": "-.-", "Л": ".-..",
    "М": "--", "Н": "-.", "О": "---", "П": ".--.", "Р": ".-.", "С": "...",
    "Т": "-", "У": "..-", "Ф": "..-.", "Х": "....", "Ц": "-.-.", "Ч": "---.",
    "Ш": "----", "Щ": "--.-", "Ъ": "--.--", "Ы": "-.--", "Ь": "-..-",
    "Э": "..-..", "Ю": "..--", "Я": ".-.-",
}


def _write_wav(path: Path, audio: np.ndarray, sr: int = 22050):
    peak = float(np.max(np.abs(audio))) or 1.0
    pcm = (audio / peak * 0.85 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def make_morse_wav(text: str, out: Path, reverse: bool = False, sr: int = 22050):
    unit = int(sr * 0.08)
    freq = 680.0
    chunks = []
    for ch in only_ru(text):
        code = MORSE_RU[ch]
        for sym in code:
            n = unit if sym == "." else 3 * unit
            t = np.arange(n) / sr
            tone = np.sin(2 * np.pi * freq * t) * np.hanning(n)
            chunks.append(tone.astype(np.float32))
            chunks.append(np.zeros(unit, dtype=np.float32))
        chunks.append(np.zeros(3 * unit, dtype=np.float32))
    audio = np.concatenate(chunks) if chunks else np.zeros(sr, dtype=np.float32)
    noise = np.random.default_rng(3).normal(0, 0.04, audio.shape).astype(np.float32)
    audio = audio + noise
    if reverse:
        audio = audio[::-1].copy()
    _write_wav(out, audio, sr)
    print(f"  N2  {out.name}  morse «{text}» reverse={reverse}")


def make_fibonacci_rhythm_wav(out: Path, sr: int = 22050):
    """Шесть групп импульсов: 1, 1, 2, 3, 5, 8."""
    counts = (1, 1, 2, 3, 5, 8)
    pulse_n = int(sr * 0.08)
    short_gap = np.zeros(int(sr * 0.10), dtype=np.float32)
    group_gap = np.zeros(int(sr * 0.65), dtype=np.float32)
    t = np.arange(pulse_n) / sr
    pulse = (np.sin(2 * np.pi * 920 * t) * np.hanning(pulse_n)).astype(np.float32)
    chunks = [np.zeros(int(sr * 0.25), dtype=np.float32)]
    for count in counts:
        for index in range(count):
            chunks.append(pulse)
            if index + 1 < count:
                chunks.append(short_gap)
        chunks.append(group_gap)
    _write_wav(out, np.concatenate(chunks), sr)
    print(f"  N2  {out.name}  rhythm groups={counts}")


def make_ballet_waltz(total_samples: int, sr: int = 22050) -> np.ndarray:
    """Короткий оригинальный вальс в духе балетной музыкальной шкатулки."""
    audio = np.zeros(total_samples, dtype=np.float32)
    beat = 0.5  # 120 BPM, размер 3/4; восемь тактов занимают 12 секунд

    def add_note(start: float, duration: float, midi: int, amplitude: float):
        first = int(start * sr)
        count = min(int(duration * sr), total_samples - first)
        if count <= 0:
            return
        time = np.arange(count) / sr
        frequency = 440.0 * 2 ** ((midi - 69) / 12)
        tone = (
            np.sin(2 * np.pi * frequency * time)
            + 0.28 * np.sin(2 * np.pi * frequency * 2 * time)
            + 0.10 * np.sin(2 * np.pi * frequency * 3 * time)
        )
        attack = max(1, int(min(0.035, duration / 4) * sr))
        release = max(1, int(min(0.16, duration / 3) * sr))
        envelope = np.ones(count, dtype=np.float32)
        envelope[:attack] = np.linspace(0, 1, attack)
        envelope[-release:] *= np.linspace(1, 0, release)
        audio[first:first + count] += (tone * envelope * amplitude).astype(np.float32)

    chords = [
        (45, 52, 57),  # A minor
        (50, 57, 62),  # D minor
        (52, 59, 68),  # E major
        (45, 52, 57),
        (41, 48, 53),  # F major
        (50, 57, 62),
        (52, 59, 68),
        (45, 52, 57),
    ]
    melody = [
        69, 72, 76, 81, 79, 76, 74, 77, 81, 80, 76, 71,
        72, 69, 72, 74, 77, 76, 71, 76, 80, 81, 76, 69,
    ]
    for bar, chord in enumerate(chords):
        bar_start = bar * 3 * beat
        add_note(bar_start, beat * 0.92, chord[0], 0.30)
        for beat_index in (1, 2):
            start = bar_start + beat_index * beat
            for note in chord[1:]:
                add_note(start, beat * 0.78, note, 0.13)
        for beat_index in range(3):
            add_note(
                bar_start + beat_index * beat,
                beat * 0.88,
                melody[bar * 3 + beat_index],
                0.22,
            )

    # Небольшое эхо смягчает синтез, но не заходит в частоты скрытого текста.
    for delay, gain in ((int(sr * 0.18), 0.20), (int(sr * 0.36), 0.10)):
        audio[delay:] += audio[:-delay] * gain
    peak = np.max(np.abs(audio)) or 1
    return audio / peak


def make_multiline_spectrogram_wav(
    lines: tuple[str, ...],
    out: Path,
    duration: float = 12.0,
    sr: int = 22050,
):
    """Прячет несколько строк спектрограммы под слышимым вальсом."""
    lines = tuple(line.upper() for line in lines)
    cols = max(len(line) * 6 - 1 for line in lines)
    rows = len(lines) * 9 - 2
    canvas = np.zeros((rows, cols), dtype=np.float32)
    for line_index, line in enumerate(lines):
        x = 0
        y = line_index * 9
        for ch in line:
            glyph = np.array(
                [[int(bit) for bit in glyph_row] for glyph_row in PIXEL_FONT_5x7[ch]],
                dtype=np.float32,
            )
            canvas[y:y + 7, x:x + 5] = glyph
            x += 6

    repeats = 4
    n_time = (cols + 2) * repeats
    n_freq = max(48, rows * 2 + 8)
    target = np.zeros((n_freq, n_time), dtype=np.float32)
    pad = (n_freq - rows * 2) // 2
    for time_index in range(n_time):
        source_x = time_index // repeats - 1
        if not 0 <= source_x < cols:
            continue
        for y in range(rows):
            if not canvas[y, source_x]:
                continue
            # Верхняя строка текста должна оказаться в верхней части спектрограммы.
            frequency_index = pad + (rows - 1 - y) * 2
            target[frequency_index:frequency_index + 2, time_index] = 1

    samples_per_column = max(int(sr * duration / n_time), 32)
    total_samples = samples_per_column * n_time
    timeline = np.arange(total_samples) / sr
    # Музыка остаётся ниже ~2.5 кГц, а скрытые буквы занимают отдельную верхнюю
    # полосу. Поэтому в обычном проигрывателе слышен вальс, а не цифровой шум.
    frequencies = 4200 + np.arange(n_freq) * (5600 / max(n_freq - 1, 1))
    hidden = np.zeros(total_samples, dtype=np.float32)
    for frequency_index in np.flatnonzero(target.any(axis=1)):
        envelope = np.repeat(target[frequency_index], samples_per_column)
        carrier = np.sin(2 * np.pi * frequencies[frequency_index] * timeline)
        hidden += (carrier * envelope).astype(np.float32)
    hidden /= np.max(np.abs(hidden)) or 1
    music = make_ballet_waltz(total_samples, sr)
    audio = music * 0.92 + hidden * 0.08
    _write_wav(out, audio, sr)
    print(f"  N2  {out.name}  waltz + spectrogram lines={lines}")


N2_KEY = "КЛЮЧ"
N2_PLAIN = "СЛАБЫЙ ИМПУЛЬС ГАСНЕТ НО НОЧНОЙ ЭФИР ЕЩЕ АККУРАТНО ХРАНИТ ЕГО ПОД СЛОЕМ ЛЬДА"
N2_CIPHER = vigenere(N2_PLAIN, N2_KEY, alphabet=RU_WITH_YO)
N2_SPECTROGRAM_LINES = (
    "ВИЖЕНЕР",
    "ЬЧЮШЁХ ЖДЪЯЙУЬ ОЮИШРР ЕЩ",
    "ЩМОШЪЗ ФЯФО ЬДР ЮВХЯОЧЭЩМ",
    "МЫЛЛАЭ РБЁ ЪЪВ ИЦЪГД ЦЗВЧ",
)
assert " ".join(N2_SPECTROGRAM_LINES[1:]) == N2_CIPHER


def make_n2():
    """Реверс-Морзе КЛЮЧ → ритм ФИБО → спектрограмма-шифртекст → СИГНАЛ."""
    make_morse_wav(N2_KEY, OUT / "n2_reversed.wav", reverse=True)
    make_fibonacci_rhythm_wav(OUT / "n2_fibo.wav")
    make_multiline_spectrogram_wav(N2_SPECTROGRAM_LINES, OUT / "n2_cipher.wav")
    print(f"  N2  vigenere-33(Ё) key={N2_KEY}: «{N2_PLAIN}» → «{N2_CIPHER}»")


# ===================================================================== N3
def make_n3():
    """Пигпен РЕШЕТКА → rail ВИЖНЕР → vigenere(РЕШЕТКА) СТРОФА → book ИСТИНА."""
    word1 = "РЕШЕТКА"
    rail_plain = "ВИЖНЕР"
    rail_c = rail_fence_enc(rail_plain, 3)
    vig_plain = "СТРОФА"
    vig_c = vigenere(vig_plain, word1)
    # book: stanza, take (line, word) → letters
    stanza = [
        "Иней кроет старые камни аллеи",
        "Свет едва касается тёмных окон",
        "Тишина лежит на низких крышах",
        "Ночь открывает давно забытый архив",
    ]
    # ИСТИНА: I need letters И С Т И Н А
    # line1 word1 Иней → И
    # line1 word3 старые → С
    # line2 word1 Свет → С too
    # Let's pick:
    # (1,1) Иней → И
    # (2,1) Свет → С
    # (2,2) едва → Е — wrong
    # Change stanza to contain ИСТИНА via first letters of selected words
    stanza = [
        "Иней трогает старые камни аллеи",          # 1,1 И
        "Сад едва касается тёмных окон",            # 2,1 С
        "Тишина лежит на низких крышах",            # 3,1 Т
        "Иней снова на ветках",                     # 4,1 И
        "Ночь открывает давно забытый архив",       # 5,1 Н
        "Архив хранит последнее слово",             # 6,1 А
    ]
    coords = "1.1  2.1  3.1  4.1  5.1  6.1"  # too obvious
    # mix word positions
    stanza = [
        "Серый иней трогает камни",                 # 1,2 иней → И
        "В саду свет едва дышит",                    # 2,3 свет → С
        "Под крышей тишина лежит",                   # 3,3 тишина → Т
        "Снова иней на ветках",                      # 4,2 иней → И
        "В этой ночи открыт архив",                  # 5,3 ночи → Н
        "Последнее слово — архив",                   # wait А from архив 6,3
    ]
    # 6: "Храни архив как начало"
    stanza = [
        "Серый иней трогает камни",        # 1.2 И
        "В саду свет едва дышит",           # 2.3 С
        "Под крышей тишина лежит",          # 3.3 Т
        "Снова иней на ветках",             # 4.2 И
        "В этой ночи открыт проход",        # 5.3 Н
        "Храни архив как начало",           # 6.2 А
    ]
    picks = [(1, 2), (2, 3), (3, 3), (4, 2), (5, 3), (6, 2)]
    got = []
    for li, wi in picks:
        w = stanza[li - 1].split()[wi - 1]
        got.append(only_ru(w)[0])
    assert "".join(got) == "ИСТИНА", got

    # page 1 pigpen
    p1 = Image.new("RGB", (1100, 620), (232, 216, 190))
    d = ImageDraw.Draw(p1)
    d.text((36, 20), "ТЕТРАДЬ · лист I   (знаки, не буквы)", fill=(80, 50, 30), font=font(26))
    x0 = 50
    for i, ch in enumerate(word1):
        draw_pigpen(d, (x0 + i * 140, 160), ch, scale=36)
    # mini-legend for А Б В
    d.text((36, 420), "образец (первые три клетки без точки = А Б В):", fill=(70, 60, 50), font=font(20))
    for i, ch in enumerate("АБВ"):
        draw_pigpen(d, (50 + i * 90, 460), ch, scale=16)
        d.text((50 + i * 90, 530), ch, fill=(70, 60, 50), font=font(18))
    hack_glitch(p1, seed=31).save(OUT / "artifact_3a.png")

    p2 = Image.new("RGB", (1100, 420), (232, 216, 190))
    d = ImageDraw.Draw(p2)
    d.text((36, 20), "ТЕТРАДЬ · лист II   зигзаг / 3 рельса", fill=(80, 50, 30), font=font(26))
    d.text((36, 140), rail_c, fill=(20, 20, 50), font=font(72))
    d.text((36, 280), "Читай как железнодорожную изгородь. Три нити.", fill=(70, 60, 50), font=font(22))
    hack_glitch(p2, seed=32).save(OUT / "artifact_3b.png")

    p3 = Image.new("RGB", (1100, 480), (232, 216, 190))
    d = ImageDraw.Draw(p3)
    d.text((36, 20), "ТЕТРАДЬ · лист III   ключ — то, что открыл лист I", fill=(80, 50, 30), font=font(24))
    d.text((36, 140), vig_c, fill=(20, 20, 50), font=font(64))
    d.text((36, 280), "Виженер. Алфавит 32 буквы, без Ё. Ключ уже у тебя.", fill=(70, 60, 50), font=font(22))
    hack_glitch(p3, seed=33).save(OUT / "artifact_3c.png")

    p4 = Image.new("RGB", (1100, 640), (232, 216, 190))
    d = ImageDraw.Draw(p4)
    d.text((36, 16), "ТЕТРАДЬ · лист IV   книжный шифр", fill=(80, 50, 30), font=font(26))
    for i, line in enumerate(stanza):
        d.text((48, 80 + i * 48), f"{i + 1}.  {line}", fill=(20, 20, 40), font=font(26))
    coord_s = "  ".join(f"{a}.{b}" for a, b in picks)
    d.text((48, 420), coord_s, fill=(140, 30, 30), font=font(36))
    d.text((48, 500), "строка.слово  →  первая буква каждого слова", fill=(70, 60, 50), font=font(22))
    hack_glitch(p4, seed=34).save(OUT / "artifact_3d.png")

    print(f"  N3  pigpen {word1}")
    print(f"  N3  rail {rail_plain} → {rail_c}")
    print(f"  N3  vig key={word1} {vig_plain} → {vig_c}")
    print(f"  N3  book {coord_s} → {''.join(got)}")


# ===================================================================== N4
def make_n4():
    """Видео: вывески Л И Н З А + один кадр HEX(ТЕНЬ) + фрагментированный QR-текст КАДР."""
    hex_word = "ТЕНЬ".encode("utf-8").hex()
    signs = list("ЛИНЗА")
    exe = ffmpeg()
    frames_dir = OUT / "_n4_frames"
    frames_dir.mkdir(exist_ok=True)
    w, h = 960, 540
    n_frames = 48
    flash_i = 27
    for i in range(n_frames):
        img = Image.new("RGB", (w, h), (18, 20, 28))
        d = ImageDraw.Draw(img)
        d.rectangle((0, 400, w, h), fill=(32, 30, 36))
        d.text((24, 16), f"REC  00:00:{i:02d}", fill=(180, 40, 40), font=font(22))
        # five shop signs
        for k, letter in enumerate(signs):
            x = 40 + k * 185
            d.rectangle((x, 160, x + 160, 280), outline=(200, 180, 80), width=3)
            d.text((x + 48, 190), letter, fill=(220, 200, 90), font=font(64))
        if i == flash_i:
            img = Image.new("RGB", (w, h), (8, 8, 8))
            d = ImageDraw.Draw(img)
            d.text((40, 200), hex_word, fill=(240, 240, 240), font=font(48))
            d.text((40, 300), "UTF-8", fill=(120, 120, 120), font=font(22))
        hack_glitch(img, seed=40 + i).save(frames_dir / f"f{i:03d}.png")

    mp4 = OUT / "artifact_4a.mp4"
    if exe:
        cmd = [
            exe, "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", "6", "-i", str(frames_dir / "f%03d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4),
        ]
        subprocess.run(cmd, check=True, timeout=60)
        print(f"  N4  video {mp4.name}  signs=ЛИНЗА  flash HEX {hex_word} = ТЕНЬ")
    else:
        print("  N4  ⚠ нет ffmpeg, только кадры")

    # still of signs
    Image.open(frames_dir / "f000.png").save(OUT / "artifact_4b.png")
    # fragmented "QR" — 4 куска с частями слова КАДР as puzzle pieces
    frag = Image.new("RGB", (900, 500), (245, 245, 245))
    d = ImageDraw.Draw(frag)
    d.text((24, 16), "Собери. Четыре обломка одной метки.", fill=(20, 20, 20), font=font(24))
    pieces = [("КА", (40, 80)), ("Д", (360, 200)), ("Р", (620, 90)), ("·", (200, 300))]
    # draw 4 irregular tiles that together read КАДР
    tiles = [
        (40, 80, 280, 260, "КА"),
        (300, 80, 540, 260, ""),
        (560, 80, 860, 260, "Д"),
        (40, 280, 860, 460, "Р"),
    ]
    # better 2x2
    tiles = [
        (40, 80, 440, 270, "К"),
        (460, 80, 860, 270, "А"),
        (40, 290, 440, 470, "Д"),
        (460, 290, 860, 470, "Р"),
    ]
    for x0, y0, x1, y1, ch in tiles:
        d.rectangle((x0, y0, x1, y1), outline=(10, 10, 10), width=4, fill=(230, 230, 220))
        # fake QR noise
        rng = np.random.default_rng(abs(hash(ch)) % (2**32))
        for _ in range(80):
            px = int(rng.integers(x0 + 8, x1 - 12))
            py = int(rng.integers(y0 + 8, y1 - 12))
            d.rectangle((px, py, px + 8, py + 8), fill=(15, 15, 15))
        d.text((x0 + 40, y0 + 50), ch, fill=(10, 10, 10), font=font(72))
    hack_glitch(frag, seed=44).save(OUT / "artifact_4c.png")
    print("  N4  shards → КАДР")


# ===================================================================== N5
def make_n5():
    """binary МОДУЛЬ + magic square ЧИСЛО + html comment HEX + lock 2-5-8-4."""
    word_bin = "МОДУЛЬ"
    bits = " ".join(f"{RU.index(ch) + 1:06b}" for ch in word_bin)

    # magic square 3x3 order reading letters
    # numbers 1..9 positions, letters placed, read 1→9 = ЧИСЛО??? 5 letters
    # 4x4 1..16, first 6 letters of ЧИСЛО + padding
    word_sq = "ЧИСЛО"
    # 3x3 siamese square
    square = [
        [8, 1, 6],
        [3, 5, 7],
        [4, 9, 2],
    ]
    # place letters of a 9-letter padding phrase whose order-by-number is ЧИСЛО????
    # We put letters in cells so that reading in number order gives Ч И С Л О X X X X
    seq = list("ЧИСЛОXXXX")
    grid_letters = [[""] * 3 for _ in range(3)]
    pos = {square[r][c]: (r, c) for r in range(3) for c in range(3)}
    for n, ch in enumerate(seq, start=1):
        r, c = pos[n]
        grid_letters[r][c] = ch

    tab = Image.new("RGB", (1100, 720), (248, 248, 252))
    d = ImageDraw.Draw(tab)
    d.text((32, 20), "ЦИФРОВАЯ ТЕНЬ · лист расчёта", fill=(30, 30, 50), font=font(28))
    d.text((32, 80), "I.  шестибитные номера букв (А=000001)", fill=(50, 50, 70), font=font(22))
    d.text((32, 130), bits, fill=(10, 10, 40), font=font(28))
    d.text((32, 200), "II.  читай клетки в порядке чисел 1…9", fill=(50, 50, 70), font=font(22))
    for r in range(3):
        for c in range(3):
            x, y = 80 + c * 140, 260 + r * 110
            d.rectangle((x, y, x + 120, y + 96), outline=(20, 20, 40), width=2)
            d.text((x + 8, y + 4), str(square[r][c]), fill=(140, 140, 160), font=font(18))
            d.text((x + 36, y + 28), grid_letters[r][c], fill=(10, 10, 30), font=font(40))
    d.text((32, 620), "XXXX в квадрате — шум. Значимы первые пять по порядку.", fill=(90, 90, 110), font=font(20))
    hack_glitch(tab, seed=51).save(OUT / "artifact_5a.png")

    html = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><title>shadow ledger</title></head>
<body>
<p>Здесь нет видимого текста, который тебе нужен.</p>
<!-- HEX UTF-8: d0bb d0be d0ba -->
<p>Если смотришь глазами — смотришь не туда.</p>
</body></html>
"""
    # ЛОК = d0bb d0be d0ba
    (OUT / "artifact_5b.html").write_text(html, encoding="utf-8")
    lock = "2584"  # fib
    print(f"  N5  binary → {word_bin}")
    print(f"  N5  square → {word_sq}")
    print(f"  N5  html comment HEX → ЛОК")
    print(f"  N5  lock (fib 2,5,8,13 truncated 4) shown in verse? → {lock}")

    lock_img = Image.new("RGB", (900, 360), (20, 20, 24))
    d = ImageDraw.Draw(lock_img)
    d.text((32, 24), "III.  замок", fill=(200, 200, 210), font=font(26))
    d.text((32, 90), "ряд, который уже встречался в другом узле,\nно здесь — только числа:", fill=(160, 160, 170), font=font(22))
    d.text((32, 190), "1  1  2  3  5  8  13  21", fill=(230, 210, 80), font=font(36))
    d.text((32, 270), "четыре средних двузначных? нет. четыре после единиц.", fill=(120, 120, 130), font=font(20))
    hack_glitch(lock_img, seed=52).save(OUT / "artifact_5c.png")
    # 2 3 5 8 → 2358  "четыре после единиц" = 2,3,5,8
    print("  N5  lock code 2358")


# ===================================================================== N6
def make_n6():
    """Атбаш → изгородь → Виженер с ключом из шага 1 → ПОРТАЛ."""
    step1_plain = "АТБАШ"
    step1_c = atbash(step1_plain)  # they see cipher, decode with atbash

    rail_plain = "ВИЖНЕР"
    rail_c = rail_fence_enc(rail_plain, 3)

    vig_plain = "ПОРТАЛ"
    vig_c = vigenere(vig_plain, "АТБАШ")

    # also A1Z26 line as first visible hook
    nums = a1z26_encode(step1_c)

    img = Image.new("RGB", (1100, 780), (18, 18, 22))
    d = ImageDraw.Draw(img)
    d.text((36, 24), "ПОСЛЕДНИЙ ЗАМОК · четыре щеколды", fill=(220, 200, 140), font=font(28))
    d.text((36, 90), "I  A1Z26  (А=01 … Я=32)", fill=(140, 140, 150), font=font(22))
    d.text((36, 130), nums, fill=(240, 240, 245), font=font(40))
    d.text((36, 210), "II  то, что получилось — пропусти через зеркало алфавита", fill=(140, 140, 150), font=font(22))
    d.text((36, 280), "III  затем — три рельса, зигзаг", fill=(140, 140, 150), font=font(22))
    d.text((36, 320), rail_c, fill=(240, 240, 245), font=font(48))
    d.text((36, 410), "IV  Виженер. Ключ — слово из щеколды II.", fill=(140, 140, 150), font=font(22))
    d.text((36, 460), vig_c, fill=(240, 220, 120), font=font(56))
    d.text((36, 560), "Алфавит везде один: 32 буквы, без Ё.", fill=(110, 110, 120), font=font(20))
    # null cipher telestich as extra confirmation of ПОРТАЛ? skip to not leak
    img.save(OUT / "artifact_6a.png")

    print(f"  N6  A1Z26 of atbash(АТБАШ)={step1_c} → {nums}")
    print(f"  N6  atbash → {step1_plain}")
    print(f"  N6  rail {rail_c} → {rail_plain}")
    print(f"  N6  vig({step1_plain}) {vig_c} → {vig_plain}")


def write_readme():
    (OUT / "README.md").write_text(
        """# Медиа ARG «Аргус-1001»

Зависимости: `pip install -r bot/tools/requirements.txt`.
Пересборка: `python3 bot/tools/make_quest_assets.py`.

Все файлы принадлежат узлам N1–N6 (см. `bot/docs/QUEST_WALKTHROUGH.md`).
`n1_card.jpg` шлётся как document, иначе Telegram сожмёт EXIF и хвост JPEG.
N2 использует связанную цепочку `n2_reversed.wav` → `n2_fibo.wav` → `n2_cipher.wav`;
в последнем файле скрытая спектрограмма наложена на слышимый вальс.
Файлы N3–N6 называются нейтрально (`artifact_*`), чтобы имя не выдавало метод решения.
""",
        encoding="utf-8",
    )


def main():
    print("ARGVS-1001 assets →", OUT)
    print("-" * 60)
    make_n1()
    make_n2()
    make_n3()
    make_n4()
    make_n5()
    make_n6()
    write_readme()
    print("-" * 60)
    print("готово")


if __name__ == "__main__":
    main()
