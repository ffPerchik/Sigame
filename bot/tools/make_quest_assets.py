#!/usr/bin/env python3
"""Генератор медиа для ARG «Аргус-1001» (6 независимых узлов, много слоёв)."""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np
import piexif
from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    from .quest_crypto import (
        RU, RU_WITH_YO, a1z26_encode, atbash, braille_encode, only_ru,
        pigpen_cell, rail_fence_enc, vigenere, wrong_layout_to_ru,
    )
except ImportError:  # запуск как `python bot/tools/make_quest_assets.py`
    from quest_crypto import (
        RU, RU_WITH_YO, a1z26_encode, atbash, braille_encode, only_ru,
        pigpen_cell, rail_fence_enc, vigenere, wrong_layout_to_ru,
    )

BOT_ROOT = Path(__file__).resolve().parent.parent
OUT = BOT_ROOT / "quest" / "images"
OUT.mkdir(parents=True, exist_ok=True)

SCRIPT_FONT = BOT_ROOT / "tools" / "fonts" / "MarckScript-Regular.ttf"
PARCHMENT_SOURCE = BOT_ROOT / "quest" / "source" / "n3_parchment.png"
PARCHMENT_SOURCE_2 = BOT_ROOT / "quest" / "source" / "n3_parchment_2.png"
PARCHMENT_SOURCE_3 = BOT_ROOT / "quest" / "source" / "n3_parchment_3.png"
PARCHMENT_SOURCE_4 = BOT_ROOT / "quest" / "source" / "n3_parchment_4.png"

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


def script_font(size: int) -> ImageFont.FreeTypeFont:
    if not SCRIPT_FONT.exists():
        raise FileNotFoundError(f"Нет каллиграфического шрифта: {SCRIPT_FONT}")
    return ImageFont.truetype(str(SCRIPT_FONT), size)


def mono_font(size: int) -> ImageFont.FreeTypeFont:
    """Моноширинный шрифт из репо — нужен для символьных сеток (решётка Кардано)."""
    candidates = [
        BOT_ROOT / "tools" / "fonts" / "DejaVuSansMono-Bold.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    raise FileNotFoundError("Нет моноширинного шрифта с кириллицей")


def parchment_page(source: Path = PARCHMENT_SOURCE) -> Image.Image:
    """Чистый портретный лист из выбранного фотографического пергамента."""
    if not source.exists():
        raise FileNotFoundError(f"Нет фона старой бумаги: {source}")
    return Image.open(source).convert("RGB").resize((1024, 1536), Image.Resampling.LANCZOS)


def centered_text(draw: ImageDraw.ImageDraw, text: str, y: int, text_font, fill):
    box = draw.textbbox((0, 0), text, font=text_font)
    width = box[2] - box[0]
    draw.text(((1024 - width) / 2, y), text, fill=fill, font=text_font)


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
def draw_pigpen(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    ch: str,
    scale=18,
    color=(58, 37, 23),
    width=3,
):
    idx = RU.index(ch)
    kind, dotted, pos = pigpen_cell(idx)
    x, y = xy
    s = scale
    # 3×3 позиции: 0 1 2 / 3 4 5 / 6 7 8
    r, c = divmod(pos, 3)
    cx, cy = x + s, y + s
    # Стенки соответствующей клетки обычной решётки 3×3.
    segments = []
    if r != 0:
        segments.append((x, y, x + 2 * s, y))
    if r != 2:
        segments.append((x, y + 2 * s, x + 2 * s, y + 2 * s))
    if c != 0:
        segments.append((x, y, x, y + 2 * s))
    if c != 2:
        segments.append((x + 2 * s, y, x + 2 * s, y + 2 * s))

    if kind == "x":
        # Вторая решётка — та же таблица 3×3, повёрнутая ромбом на 45°.
        # Так все девять позиций остаются различимыми, в отличие от четырёх
        # повторяющихся углов обычного X.
        root_half = 2 ** -0.5

        def rotate_point(px, py):
            dx, dy = px - cx, py - cy
            return (
                cx + (dx - dy) * root_half,
                cy + (dx + dy) * root_half,
            )

        segments = [
            (*rotate_point(x1, y1), *rotate_point(x2, y2))
            for x1, y1, x2, y2 in segments
        ]

    for segment in segments:
        draw.line(segment, fill=color, width=width)
    if dotted:
        draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=color)


def draw_pigpen_diamond_key(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    cell=34,
    color=(58, 37, 23),
    width=5,
    letters="ТУФХЦЧШЩЪ",
):
    """Ромбическая решётка 3×3 с буквами третьей девятки алфавита."""
    if len(letters) != 9:
        raise ValueError("Для ромбической решётки нужны ровно 9 букв")
    cx, cy = center
    half = 1.5 * cell
    root_half = 2 ** -0.5

    def rotate_point(px, py):
        dx, dy = px - cx, py - cy
        return (
            cx + (dx - dy) * root_half,
            cy + (dx + dy) * root_half,
        )

    # Только внутренние линии: ромб остаётся открытой сеткой без обводки.
    for offset in (-cell / 2, cell / 2):
        vertical = (*rotate_point(cx + offset, cy - half), *rotate_point(cx + offset, cy + half))
        horizontal = (*rotate_point(cx - half, cy + offset), *rotate_point(cx + half, cy + offset))
        draw.line(vertical, fill=color, width=width)
        draw.line(horizontal, fill=color, width=width)

    letter_font = script_font(max(18, int(cell * 0.64)))
    for position, letter in enumerate(letters):
        row, column = divmod(position, 3)
        letter_x, letter_y = rotate_point(
            cx + (column - 1) * cell,
            cy + (row - 1) * cell,
        )
        draw.text(
            (letter_x, letter_y),
            letter,
            fill=color,
            font=letter_font,
            anchor="mm",
        )


def draw_pigpen_square_key(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    cell=42,
    color=(58, 37, 23),
    width=5,
    letters="АБВГДЕЖЗИ",
):
    """Открытая решётка 3×3 с первыми буквами — без внешней обводки."""
    if len(letters) != 9:
        raise ValueError("Для квадратной решётки нужны ровно 9 букв")
    cx, cy = center
    half = 1.5 * cell
    for offset in (-cell / 2, cell / 2):
        draw.line((cx + offset, cy - half, cx + offset, cy + half), fill=color, width=width)
        draw.line((cx - half, cy + offset, cx + half, cy + offset), fill=color, width=width)

    letter_font = script_font(max(18, int(cell * 0.64)))
    for position, letter in enumerate(letters):
        row, column = divmod(position, 3)
        draw.text(
            (cx + (column - 1) * cell, cy + (row - 1) * cell),
            letter,
            fill=color,
            font=letter_font,
            anchor="mm",
        )


def burn_lower_left_corner(page: Image.Image) -> Image.Image:
    """Выжигает неровный кусок страницы, скрывая левую половину ромба."""
    edge = [
        (48, 1105), (69, 1142), (82, 1180), (116, 1206),
        (132, 1238), (164, 1263), (153, 1290), (178, 1315),
        (154, 1343), (166, 1371), (137, 1397), (120, 1430),
        (88, 1468),
    ]

    # Мягкий ореол копоти остаётся на сохранившейся бумаге.
    rgba = page.convert("RGBA")
    soot = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    soot_draw = ImageDraw.Draw(soot)
    soot_draw.line(edge, fill=(46, 19, 6, 170), width=62, joint="curve")
    soot = soot.filter(ImageFilter.GaussianBlur(15))
    rgba = Image.alpha_composite(rgba, soot)

    burned = ImageDraw.Draw(rgba)
    cutout = [(0, 1090), *edge, (0, 1536)]
    burned.polygon(cutout, fill=(255, 255, 255, 255))

    # Тонкая угольная кромка поверх размытой копоти — без нарисованной
    # «коричневой обводки», чтобы прогар сливался с фотографией листа.
    char = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    char_draw = ImageDraw.Draw(char)
    char_draw.line(edge, fill=(73, 33, 12, 165), width=22, joint="curve")
    char_draw.line(edge, fill=(19, 9, 4, 235), width=7, joint="curve")
    for x, y, radius in (
        (90, 1167, 5), (128, 1221, 4), (170, 1281, 6),
        (165, 1355, 4), (132, 1411, 6), (92, 1455, 4),
    ):
        char_draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=(28, 13, 5, 205),
        )
    char = char.filter(ImageFilter.GaussianBlur(1.2))
    return Image.alpha_composite(rgba, char).convert("RGB")


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


DTMF_FREQUENCIES = {
    "1": (697, 1209), "2": (697, 1336), "3": (697, 1477),
    "4": (770, 1209), "5": (770, 1336), "6": (770, 1477),
    "7": (852, 1209), "8": (852, 1336), "9": (852, 1477),
    "0": (941, 1336),
}
N2_DTMF_DIGITS = "112358"


def make_dtmf_sequence_wav(out: Path, sr: int = 22050):
    """Телефонными DTMF-сигналами набирает 1-1-2-3-5-8."""
    tone_seconds = 0.26
    gap_seconds = 0.12
    tone_samples = int(sr * tone_seconds)
    gap = np.zeros(int(sr * gap_seconds), dtype=np.float32)
    edge = max(1, int(sr * 0.015))
    envelope = np.ones(tone_samples, dtype=np.float32)
    envelope[:edge] = np.linspace(0, 1, edge)
    envelope[-edge:] = np.linspace(1, 0, edge)
    time = np.arange(tone_samples) / sr
    chunks = [np.zeros(int(sr * 0.20), dtype=np.float32)]
    for index, digit in enumerate(N2_DTMF_DIGITS):
        low, high = DTMF_FREQUENCIES[digit]
        tone = 0.5 * (
            np.sin(2 * np.pi * low * time)
            + np.sin(2 * np.pi * high * time)
        )
        chunks.append((tone * envelope).astype(np.float32))
        if index + 1 < len(N2_DTMF_DIGITS):
            chunks.append(gap)
    chunks.append(np.zeros(int(sr * 0.20), dtype=np.float32))
    _write_wav(out, np.concatenate(chunks), sr)
    print(f"  N2  {out.name}  DTMF digits={N2_DTMF_DIGITS}")


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
    """Реверс-Морзе КЛЮЧ → DTMF 112358 → спектрограмма-шифртекст → СИГНАЛ."""
    make_morse_wav(N2_KEY, OUT / "n2_1.wav", reverse=True)
    make_dtmf_sequence_wav(OUT / "n2_2.wav")
    make_multiline_spectrogram_wav(N2_SPECTROGRAM_LINES, OUT / "n2_3.wav")
    print(f"  N2  vigenere-33(Ё) key={N2_KEY}: «{N2_PLAIN}» → «{N2_CIPHER}»")


# ===================================================================== N3
def make_n3():
    """Четыре реалистичных листа: pigpen → rail → Polybius → pigpen-решётка."""
    word1 = "РЕШЕТКА"
    crib = "СИКССЕВЕН"
    # Рельсы называют новый метод, не повторяя Виженера из N2.
    rail_plain = "СЛЕДУЮЩИЙШИФРНОСИТИМЯПОЛИБИЯ"
    rail_c = rail_fence_enc(rail_plain, 3)
    rail_pattern = [index % 4 if index % 4 <= 2 else 4 - index % 4 for index in range(len(rail_plain))]
    rail_counts = [rail_pattern.count(rail) for rail in range(3)]
    rail_rows = []
    rail_cursor = 0
    for count in rail_counts:
        rail_rows.append(rail_c[rail_cursor:rail_cursor + count])
        rail_cursor += count
    assert rail_counts == [7, 14, 7]
    assert "".join(rail_rows) == rail_c

    polybius_plain = "СЮЖЕТЫ"
    polybius_alphabet = "".join(dict.fromkeys(word1 + RU_WITH_YO))
    polybius_pairs = []
    for letter in polybius_plain:
        index = polybius_alphabet.index(letter)
        polybius_pairs.append(f"{index // 6 + 1}{index % 6 + 1}")
    assert len(polybius_alphabet) == 33
    assert polybius_pairs == ["43", "62", "26", "12", "14", "55"]
    # Финал: шапка — перемешанная СЮЖЕТЫ. Сортировка даёт 361245.
    # Первая цифра пар листа III меняется на место этой цифры в 361245.
    # На листе IV пара читается наоборот: сначала столбец, потом строка.
    keyword = polybius_plain
    header_key = "ЖЕСТЫЮ"
    assert sorted(header_key) == sorted(keyword)
    assert header_key != keyword
    sort_order = [header_key.index(letter) + 1 for letter in keyword]
    assert sort_order == [3, 6, 1, 2, 4, 5]
    answer4 = "ПРАВДА"
    picks = []
    for pair in polybius_pairs:
        column, row = int(pair[0]), int(pair[1])
        picks.append((row, sort_order.index(column) + 1))
    assert picks == [(3, 5), (2, 2), (6, 4), (2, 3), (4, 3), (5, 6)]
    assert len(set(picks)) == len(picks) == len(answer4) == 6
    grid_letters = [[""] * 6 for _ in range(6)]
    for (row, column), letter in zip(picks, answer4):
        grid_letters[row - 1][column - 1] = letter
    noise = [ch for ch in RU if ch not in answer4]
    for row in range(6):
        for column in range(6):
            if not grid_letters[row][column]:
                grid_letters[row][column] = noise[(row * 7 + column * 3) % len(noise)]
    got = [grid_letters[row - 1][column - 1] for row, column in picks]
    assert "".join(got) == answer4, got

    ink = (62, 39, 23)
    faded_ink = (92, 62, 39)
    accent = (112, 43, 31)

    # Лист I: автор объясняет свой язык на словах «сикс севен», затем даёт загадку.
    page1 = parchment_page()
    draw = ImageDraw.Draw(page1)
    centered_text(draw, "Лист I", 75, script_font(76), ink)
    centered_text(draw, "Решил создать новый язык,", 185, script_font(43), faded_ink)
    centered_text(draw, "вот так вот будет на нём звучать", 245, script_font(43), faded_ink)
    centered_text(draw, "моё любимое слово", 305, script_font(43), faded_ink)

    label_font = script_font(50)
    label_x, label_y = 90, 400
    draw.text((label_x, label_y), "«сикс севен»", fill=ink, font=label_font)
    label_box = draw.textbbox((label_x, label_y), "«сикс севен»", font=label_font)
    arrow_x = label_box[2] + 15
    arrow_y = 436
    draw.line((arrow_x, arrow_y, arrow_x + 38, arrow_y), fill=ink, width=4)
    draw.polygon(
        [(arrow_x + 38, arrow_y), (arrow_x + 27, arrow_y - 8), (arrow_x + 27, arrow_y + 8)],
        fill=ink,
    )
    cipher_x = arrow_x + 53
    for index, letter in enumerate(crib):
        draw_pigpen(draw, (cipher_x + index * 49, 416), letter, scale=11, color=ink, width=5)

    draw.line((120, 565, 900, 565), fill=faded_ink, width=2)

    # Сначала рисуем послание одной горизонтальной строкой, затем целиком
    # поворачиваем её на 45°: вместе со строкой поворачивается каждый знак.
    message_strip = Image.new("RGBA", (610, 105), (0, 0, 0, 0))
    strip_draw = ImageDraw.Draw(message_strip)
    for index, letter in enumerate(word1):
        draw_pigpen(
            strip_draw,
            (25 + index * 82, 27),
            letter,
            scale=23,
            color=(*ink, 255),
            width=7,
        )
    rotated_message = message_strip.rotate(
        -45,
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )
    page1.paste(rotated_message, (315, 655), rotated_message)

    # Слева — ромбическая третья девятка, справа — прямая первая девятка.
    draw_pigpen_diamond_key(draw, (175, 1305), cell=42, color=ink, width=6)
    draw_pigpen_square_key(draw, (820, 1305), cell=42, color=ink, width=6)
    page1 = burn_lower_left_corner(page1)
    page1.save(OUT / "artifact_3a.png", optimize=True)

    # Лист II: длинная фраза разложена по трём рельсам — взглядом ответ не угадать.
    page2 = parchment_page(PARCHMENT_SOURCE_2)
    draw = ImageDraw.Draw(page2)
    centered_text(draw, "Лист II", 105, script_font(82), ink)
    centered_text(draw, "строка помнит путь, которым её писали", 225, script_font(42), faded_ink)
    for row, y, size in zip(rail_rows, (440, 585, 730), (84, 68, 84)):
        centered_text(draw, row, y, script_font(size), ink)

    rail_y = (990, 1060, 1130)
    for y in rail_y:
        draw.line((145, y, 880, y), fill=(112, 83, 57), width=2)
    path = []
    pattern = (0, 1, 2, 1)
    for index in range(17):
        path.append((150 + index * 45, rail_y[pattern[index % 4]]))
    draw.line(path, fill=faded_ink, width=4, joint="curve")
    centered_text(draw, "три следа — одна строка", 1240, script_font(48), faded_ink)
    page2.save(OUT / "artifact_3b.png", optimize=True)

    # Лист III: квадрат Полибия 6×6 начинается с уникальных букв первого ответа.
    page3 = parchment_page(PARCHMENT_SOURCE_3)
    draw = ImageDraw.Draw(page3)
    centered_text(draw, "Лист III", 85, script_font(82), ink)

    # Настоящая пометка на полях: вся строка повёрнута на 90° вдоль левого края.
    margin_text = "«первое слово начинает алфавит»"
    margin_font = script_font(40)
    margin_box = draw.textbbox((0, 0), margin_text, font=margin_font)
    margin_layer = Image.new(
        "RGBA",
        (margin_box[2] - margin_box[0] + 24, margin_box[3] - margin_box[1] + 24),
        (0, 0, 0, 0),
    )
    ImageDraw.Draw(margin_layer).text(
        (12 - margin_box[0], 12 - margin_box[1]),
        margin_text,
        fill=(*faded_ink, 255),
        font=margin_font,
    )
    margin_layer = margin_layer.rotate(90, resample=Image.Resampling.BICUBIC, expand=True)
    page3.paste(margin_layer, (82, 340), margin_layer)
    draw = ImageDraw.Draw(page3)

    grid_x, grid_y, cell = 245, 355, 85
    grid_size = cell * 6
    label_font = script_font(32)
    for index in range(7):
        offset = index * cell
        draw.line((grid_x + offset, grid_y, grid_x + offset, grid_y + grid_size), fill=ink, width=3)
        draw.line((grid_x, grid_y + offset, grid_x + grid_size, grid_y + offset), fill=ink, width=3)
    for index in range(6):
        draw.text(
            (grid_x + index * cell + cell / 2, grid_y - 35),
            str(index + 1), fill=faded_ink, font=label_font, anchor="mm",
        )
        draw.text(
            (grid_x - 32, grid_y + index * cell + cell / 2),
            str(index + 1), fill=faded_ink, font=label_font, anchor="mm",
        )

    # Две заполненные клетки помогают проверить построение ключевого алфавита.
    given_font = script_font(52)
    for (row, column), letter in {(2, 5): "Ё", (6, 3): "Я"}.items():
        draw.text(
            (grid_x + (column - 0.5) * cell, grid_y + (row - 0.5) * cell),
            letter, fill=ink, font=given_font, anchor="mm",
        )

    centered_text(draw, "  ".join(polybius_pairs), 1035, script_font(82), accent)
    page3.save(OUT / "artifact_3c.png", optimize=True)

    # Лист IV: шапка — перемешанная СЮЖЕТЫ. Сортировка даёт координаты.
    page4 = parchment_page(PARCHMENT_SOURCE_4)
    draw = ImageDraw.Draw(page4)
    centered_text(draw, "Лист IV", 70, script_font(82), ink)
    centered_text(draw, "верхний ряд сбился с порядка", 170, script_font(40), faded_ink)
    centered_text(draw, "третье слово знает, как его вернуть", 230, script_font(38), faded_ink)

    grid_x, grid_y, cell = 245, 430, 85
    grid_size = cell * 6
    label_font = script_font(32)
    for index in range(7):
        offset = index * cell
        draw.line((grid_x + offset, grid_y, grid_x + offset, grid_y + grid_size), fill=ink, width=3)
        draw.line((grid_x, grid_y + offset, grid_x + grid_size, grid_y + offset), fill=ink, width=3)
    header_scale = 13
    cell_scale = 18
    for index, letter in enumerate(header_key):
        draw.text(
            (grid_x + index * cell + cell / 2, grid_y - 88),
            str(index + 1), fill=faded_ink, font=label_font, anchor="mm",
        )
        draw_pigpen(
            draw,
            (
                int(grid_x + index * cell + cell / 2 - header_scale),
                grid_y - 68,
            ),
            letter,
            scale=header_scale,
            color=ink,
            width=4,
        )
        draw.text(
            (grid_x - 32, grid_y + index * cell + cell / 2),
            str(index + 1), fill=faded_ink, font=label_font, anchor="mm",
        )
    for row in range(6):
        for column in range(6):
            draw_pigpen(
                draw,
                (
                    int(grid_x + column * cell + cell / 2 - cell_scale),
                    int(grid_y + row * cell + cell / 2 - cell_scale),
                ),
                grid_letters[row][column],
                scale=cell_scale,
                color=ink,
                width=5,
            )
    centered_text(draw, "язык первого листа ещё нужен", 1185, script_font(40), faded_ink)
    page4.save(OUT / "artifact_3d.png", optimize=True)

    print(f"  N3  pigpen {word1}; crib {crib}")
    print(f"  N3  rail {rail_plain} → {rail_c}")
    print(f"  N3  polybius key={word1} {polybius_plain} → {' '.join(polybius_pairs)}")
    print(f"  N3  pigpen-grid header={header_key} sort={sort_order} {polybius_pairs} → {picks} → {''.join(got)}")


# ===================================================================== N4
def make_n4():
    """N4 «НАБЛЮДЕНИЕ» переехал на реальную съёмку + YouTube + QR.

    Ассеты собирает отдельный инструмент: bot/tools/make_n4_video.py
    (исходник — сток в bot/quest/source/, вывод — artifact_4a/4b/4c).
    """
    print("  N4  пропущено: см. bot/tools/make_n4_video.py (YouTube CCTV + QR)")


# ===================================================================== N5
def make_n5():
    """binary МОДУЛЬ + magic square ЧИСЛО + html comment HEX + lock 2358."""
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
    lock = "2358"  # четыре числа после двух единиц в ряду Фибоначчи
    print(f"  N5  binary → {word_bin}")
    print(f"  N5  square → {word_sq}")
    print(f"  N5  html comment HEX → ЛОК")
    print(f"  N5  lock code → {lock}")

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
# Узел «ТАЙНИК»: четыре носителя (бумага, видео, пластина, записка) и четыре
# новых приёма (решётка Кардано, чужая раскладка, брайль, акростих).
N6_LETTER_LINES = [
    "если ты читаешь это",
    "я успел собрать сейф",
    "вниз под полосой",
    "не верь аргусу он врёт",
    "держи этот лист твёрдо",
    "проверь раму окна",
    "ключи и шкафы",
    "и не ищи меня в сети",
]
# (строка, колонка) дырок решётки; чтение по порядку строк даёт ТИТРЫ.
N6_GRILLE_HOLES = [(1, 13), (2, 2), (4, 7), (5, 1), (6, 12)]
# Субтитр в ролике набран в физической раскладке QWERTY; в ЙЦУКЕН это ТОЧКИ.
N6_LAYOUT_CAPTION = "njxrb"
# Финал: Виженер с ключом ФИНАЛ (первые буквы слов Жени из фрагментов N1–N5).
N6_FINAL_CIPHER = "ЪНЪЯСЬК"
N6_NOTE_LINES = [
    "если ты дошёл до этого места — ты собрал все пять моих слов.",
    "ключ — их первые буквы, в порядке узлов.",
    "то, что я не мог сказать вслух, записано ниже.",
    "",
    "ЪНЪЯСЬК",
    "",
    "жди меня. я вернусь, когда аргус отвлечётся.",
]


def _grille_extract(lines, holes):
    return "".join(lines[r][c] for r, c in sorted(holes))


def make_n6():
    """Тайник Жени: письмо+плёнка (Кардано), ролик (раскладка), брайль, акростих."""
    assert _grille_extract(N6_LETTER_LINES, N6_GRILLE_HOLES).upper() == "ТИТРЫ"
    assert wrong_layout_to_ru(N6_LAYOUT_CAPTION) == "точки"
    assert vigenere(N6_FINAL_CIPHER, "ФИНАЛ", decrypt=True) == "ЖЕНЯЖИВ"
    assert N6_FINAL_CIPHER in N6_NOTE_LINES

    w, h = 1000, 700
    mono = mono_font(30)
    cw = mono.getlength("ММММ") / 4
    x0, y0, line_h = 60, 160, 54

    # --- письмо (бумага) ---
    letter = Image.new("RGB", (w, h), (236, 230, 212))
    d = ImageDraw.Draw(letter)
    d.text((x0, 40), "НЕ ОТПРАВЛЕНО", fill=(160, 50, 45), font=font(28))
    d.text((x0, 90), "черновик · монитор k@ly$%ev", fill=(120, 110, 90), font=font(20))
    for r, line in enumerate(N6_LETTER_LINES):
        for c, ch in enumerate(line):
            d.text((x0 + c * cw, y0 + r * line_h), ch, fill=(35, 32, 40), font=mono)
    for mx, my in ((24, 24), (w - 44, 24), (24, h - 44)):
        d.rectangle((mx, my, mx + 20, my + 20), fill=(30, 30, 30))
    text_rect = (40, 120, w - 40, y0 + len(N6_LETTER_LINES) * line_h + 16)
    hack_glitch(letter, seed=61, keep_rect=text_rect, power=0.7).save(
        OUT / "artifact_6a.png"
    )

    # --- обгоревшая плёнка с дырками (решётка Кардано) ---
    film = Image.new("RGB", (w, h), (12, 12, 14))
    d = ImageDraw.Draw(film)
    for r, c in N6_GRILLE_HOLES:
        cx, cy = x0 + c * cw + cw / 2, y0 + r * line_h + 20
        d.ellipse((cx - cw * 0.75, cy - 24, cx + cw * 0.75, cy + 24), fill=(236, 230, 212))
        d.ellipse(
            (cx - cw * 0.75 - 5, cy - 29, cx + cw * 0.75 + 5, cy + 29),
            outline=(70, 60, 50), width=5,
        )
    for mx, my in ((24, 24), (w - 44, 24), (24, h - 44)):
        d.rectangle((mx, my, mx + 20, my + 20), fill=(230, 230, 230))
    hack_glitch(film, seed=62, power=0.8).save(OUT / "artifact_6b.png")
    print(f"  N6  grille holes → {_grille_extract(N6_LETTER_LINES, N6_GRILLE_HOLES)}")

    # --- ролик с монитора: субтитр в чужой раскладке ---
    exe = ffmpeg()
    frames_dir = OUT / "_n6_frames"
    frames_dir.mkdir(exist_ok=True)
    vw, vh = 960, 540
    n_frames = 40
    for i in range(n_frames):
        img = Image.new("RGB", (vw, vh), (16, 18, 24))
        d = ImageDraw.Draw(img)
        d.text((24, 16), f"REC  00:00:{i:02d}", fill=(180, 40, 40), font=font(22))
        d.text((vw - 320, 16), "захват · монитор k@ly$%ev", fill=(110, 110, 120), font=font(18))
        d.rectangle((60, 80, vw - 60, vh - 120), outline=(70, 74, 86), width=2)
        d.text((80, 96), "блокнот — без названия", fill=(150, 150, 160), font=font(20))
        if i % 2 == 0:  # мигающий курсор
            d.rectangle((84, 150, 96, 178), fill=(220, 220, 225))
        if i >= 16:
            d.text((250, vh - 90), N6_LAYOUT_CAPTION, fill=(215, 215, 220), font=font(36))
            d.text((250, vh - 44), "субтитры: авто", fill=(100, 100, 110), font=font(16))
        hack_glitch(img, seed=63 + i).save(frames_dir / f"f{i:03d}.png")

    Image.open(frames_dir / "f020.png").save(OUT / "artifact_6d.png")
    if exe:
        cmd = [
            exe, "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", "6", "-i", str(frames_dir / "f%03d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(OUT / "artifact_6c.mp4"),
        ]
        subprocess.run(cmd, check=True, timeout=60)
        print(f"  N6  video caption {N6_LAYOUT_CAPTION} → {wrong_layout_to_ru(N6_LAYOUT_CAPTION)}")
    else:
        print("  N6  ⚠ нет ffmpeg, только кадры")

    # --- пластина с брайлем ---
    from PIL.PngImagePlugin import PngInfo

    pw, ph = 980, 380
    plate = Image.new("RGB", (pw, ph), (26, 28, 34))
    d = ImageDraw.Draw(plate)
    d.text((32, 24), "ПЛАСТИНА · дубль на ощупь", fill=(150, 150, 160), font=font(24))
    cells = braille_encode("СТРОКИ")
    for idx, cell in enumerate(cells):
        bx = 60 + idx * 150
        by = 140
        dots = {int(v) for v in cell}
        for dot in range(1, 7):
            dx = bx + (0 if dot in (1, 2, 3) else 56)
            dy = by + {1: 0, 2: 52, 3: 104, 4: 0, 5: 52, 6: 104}[dot]
            if dot in dots:
                d.ellipse((dx, dy, dx + 34, dy + 34), fill=(226, 222, 208))
                d.ellipse((dx + 6, dy + 6, dx + 18, dy + 18), fill=(250, 248, 240))
            else:
                d.ellipse((dx, dy, dx + 34, dy + 34), outline=(60, 62, 70), width=2)
    meta = PngInfo()
    meta.add_text("note", "точки — это буквы. считай, не смотри.")
    hack_glitch(plate, seed=64, power=0.5).save(OUT / "artifact_6e.png", pnginfo=meta)
    print(f"  N6  braille cells {' '.join(cells)} → СТРОКИ")

    # --- записка-акростих ---
    (OUT / "artifact_6f.txt").write_text(
        "\n".join(N6_NOTE_LINES) + "\n", encoding="utf-8"
    )
    print(f"  N6  note cipher {N6_FINAL_CIPHER} (ключ ФИНАЛ) → ЖЕНЯ ЖИВ")


def write_readme():
    (OUT / "README.md").write_text(
        """# Медиа ARG «Аргус-1001»

Зависимости: `pip install -r bot/tools/requirements.txt`.
Пересборка: `python3 bot/tools/make_quest_assets.py`.

Все файлы принадлежат узлам N1–N6 (см. `bot/docs/QUEST_WALKTHROUGH.md`).
`n1_card.jpg` шлётся как document, иначе Telegram сожмёт EXIF и хвост JPEG.
N2 использует связанную цепочку `n2_1.wav` → `n2_2.wav` → `n2_3.wav`;
в последнем файле скрытая спектрограмма наложена на слышимый вальс.
Файлы N3–N6 называются нейтрально (`artifact_*`), чтобы имя не выдавало метод решения.
Все четыре листа N3 используют отдельные фоны `quest/source/n3_parchment*.png`. Шрифт — Marck Script (SIL OFL 1.1).
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
