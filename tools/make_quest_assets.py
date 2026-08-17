#!/usr/bin/env python3
"""Генератор ассетов для ARG-квеста «Аргус-1001» (bot/quest/images/).

Создаёт (или пересоздаёт) все нужные файлы, на которые ссылаются
стадии в bot/quest/stages.yaml:

  n1_clue.jpg     — фото Москвы (Воробьёвы горы) с EXIF GPS
  n2_audio1.wav   — «АРГУС» в спектрограмме
  n2_audio2.wav   — «СЛЕД» в спектрограмме
  n3_page1.png    — страница дневника с подстановкой («ИЩИ» → ...)
  n3_page2.png    — страница с Цезарем («СВЕТ» → «...»)
  n4_walk.mp4     — короткая видео-прогулка (плейсхолдер 5 сек → заменишь)
  n5_table.png    — таблица часов/минут/секунд → координаты
  n6_cipher.png   — цепочка A1Z26 → Цезарь

Запуск:
    python3 tools/make_quest_assets.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import piexif
from PIL import Image, ImageDraw, ImageFont

# ---- пути ----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
SRC_PHOTO = ROOT / "content" / "stego_carrier.jpg"      # база для n1
OUT_DIR = ROOT / "bot" / "quest" / "images"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font_path() -> str | None:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


# ========================================================================== N1
def make_n1_clue() -> Path:
    """Копия stego_carrier.jpg с EXIF GPS для Воробьёвых гор."""
    out = OUT_DIR / "n1_clue.jpg"
    if not SRC_PHOTO.exists():
        raise FileNotFoundError(f"нет {SRC_PHOTO}")
    img = Image.open(SRC_PHOTO).convert("RGB")

    lat, lon = 55.7105, 37.5404

    def _gps_rational(decimal: float):
        deg = int(decimal)
        mfloat = (decimal - deg) * 60
        m = int(mfloat)
        s = round((mfloat - m) * 60 * 100)
        return ((deg, 1), (m, 1), (s, 100))

    gps_ifd = {
        piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: _gps_rational(lat),
        piexif.GPSIFD.GPSLongitudeRef: b"E",
        piexif.GPSIFD.GPSLongitude: _gps_rational(lon),
    }
    exif_bytes = piexif.dump({"GPS": gps_ifd})
    img.save(out, "JPEG", quality=88, optimize=True, exif=exif_bytes)
    print(f"  n1_clue.jpg  ←  {SRC_PHOTO.name} + EXIF GPS {lat}, {lon}")
    return out


# ========================================================================== N2
# 5×7 пиксельный шрифт кириллицы. Каждая буква — массив из 7 строк по 5 «1/0».
PIXEL_FONT_5x7: dict[str, list[str]] = {
    "А": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "Б": ["11111", "10000", "10000", "11110", "10001", "10001", "11110"],
    "В": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "Г": ["11111", "10000", "10000", "10000", "10000", "10000", "10000"],
    "Д": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "Е": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "Ж": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "З": ["01110", "10001", "00001", "00110", "00001", "10001", "01110"],
    "И": ["10001", "10001", "10011", "10101", "11001", "10001", "10001"],
    "Й": ["00100", "10001", "10011", "10101", "11001", "10001", "10001"],
    "К": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "Л": ["00001", "00001", "00001", "00001", "10001", "10001", "01110"],
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
    "Ц": ["10001", "10001", "10001", "10001", "10001", "10001", "11110"],
    "Ч": ["10001", "10001", "10001", "01111", "00001", "00001", "00001"],
    "Ш": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "Щ": ["10001", "10001", "10001", "10001", "10001", "10001", "11111"],
    "Ъ": ["11000", "01000", "01110", "01001", "01001", "01001", "01110"],
    "Ы": ["10001", "10001", "10001", "01101", "01011", "01011", "01101"],
    "Ь": ["11110", "10000", "10000", "11110", "10001", "10001", "11110"],
    "Э": ["01110", "10001", "00001", "00110", "00001", "10001", "01110"],
    "Ю": ["10010", "10101", "10101", "11101", "10101", "10101", "10010"],
    "Я": ["01110", "10001", "10001", "01110", "01010", "10001", "10001"],
}


def make_word_spectrogram_wav(text: str, out: Path, duration: float = 4.0,
                               sr: int = 22050, n_freq: int = 28,
                               n_time_per_pixel: int = 6,
                               f_min: int = 700, f_max: int = 6500) -> Path:
    """WAV-файл, в спектрограмме которого виден текст (5×7 пиксельный шрифт).

    Растр букв разворачивается в сетку (n_freq × n_time) и затем в звук:
    в каждом временном слоте активны только частоты, соответствующие
    горящим пикселям текста.
    """
    import wave
    text = text.upper()
    unknown = [ch for ch in text if ch not in PIXEL_FONT_5x7]
    if unknown:
        raise ValueError(f"нет глифов для: {set(unknown)} — добавь в PIXEL_FONT_5x7")

    cols = len(text) * 6 - 1
    rows = 7
    raw = np.zeros((rows, cols), dtype=np.float32)
    x = 0
    for ch in text:
        glyph = np.array([[int(c) for c in line] for line in PIXEL_FONT_5x7[ch]],
                         dtype=np.float32)
        raw[:, x:x + 5] = glyph
        x += 6

    freq_h = rows * 2
    pad_top = max(0, (n_freq - freq_h) // 2)
    n_time = cols * n_time_per_pixel + 8
    target = np.zeros((n_freq, n_time), dtype=np.float32)
    for ti in range(n_time):
        src_col = min(cols - 1, ti // n_time_per_pixel)
        for r in range(rows):
            v = raw[r, src_col]
            if v:
                if pad_top + r * 2 < n_freq:
                    target[pad_top + r * 2, ti] = 1.0
                if pad_top + r * 2 + 1 < n_freq:
                    target[pad_top + r * 2 + 1, ti] = 1.0

    samples_per_col = max(int(sr * duration / n_time), 32)
    total = samples_per_col * n_time
    audio = np.zeros(total, dtype=np.float32)
    t_local = np.arange(samples_per_col) / sr
    freqs = f_min + np.arange(n_freq) * (f_max - f_min) / max(n_freq - 1, 1)
    wave_mat = np.sin(2 * np.pi * freqs[:, None] * t_local[None, :]).astype(np.float32)
    for ci in range(n_time):
        active = target[:, ci] > 0.5
        if not active.any():
            continue
        col_audio = wave_mat[active].sum(axis=0).astype(np.float32)
        peak = float(np.max(np.abs(col_audio)))
        if peak > 1e-6:
            col_audio = col_audio / peak * 0.85
        audio[ci * samples_per_col:(ci + 1) * samples_per_col] = col_audio

    fade = max(1, int(sr * 0.1))
    audio[:fade] *= np.linspace(0, 1, fade) ** 1.5
    audio[-fade:] *= np.linspace(1, 0, fade) ** 1.5
    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        audio = audio / peak * 0.85
    pcm = (audio * 32767).astype(np.int16)
    tail = np.zeros(int(sr * 0.6), dtype=np.int16)
    full = np.concatenate([pcm, tail])

    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(full.tobytes())

    print(f"  {out.name:<14}  ←  ⌜{text}⌝ в спектрограмме ({duration:.1f} с)")
    return out


# ========================================================================== N3
SUBST_ALPHA = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"   # 32


def _build_subst_key(seed: int) -> dict[str, str]:
    rng = np.random.default_rng(seed)
    perm = list(SUBST_ALPHA)
    rng.shuffle(perm)
    return {a: b for a, b in zip(SUBST_ALPHA, perm)}


def _apply_subst(plain: str, key: dict[str, str]) -> str:
    return "".join(key.get(ch.upper(), ch) for ch in plain)


def make_n3_page1() -> Path:
    """Подстановка: «ИЩИ» зашифровано + ключ внизу."""
    out = OUT_DIR / "n3_page1.png"
    key = _build_subst_key(seed=11)
    line1 = "СТАРЫЙ ДНЕВНИК"
    line2 = "ИЩИ"
    line3 = "В ТИШИНЕ"
    c1 = _apply_subst(line1, key)
    c2 = _apply_subst(line2, key)
    c3 = _apply_subst(line3, key)

    W, H = 980, 540
    img = Image.new("RGB", (W, H), (235, 220, 200))
    draw = ImageDraw.Draw(img)
    fp = _font_path()
    big = ImageFont.truetype(fp, 64) if fp else ImageFont.load_default()
    mid = ImageFont.truetype(fp, 36) if fp else ImageFont.load_default()
    small = ImageFont.truetype(fp, 22) if fp else ImageFont.load_default()

    draw.text((40, 24), "ДНЕВНИК · стр. 11", fill=(80, 60, 30), font=mid)
    draw.text((40, 80), c1, fill=(20, 20, 60), font=big)
    draw.text((40, 200), c2, fill=(160, 30, 30), font=big)
    draw.text((40, 320), c3, fill=(20, 20, 60), font=big)
    draw.text((40, 430), "Ключ подстановки:", fill=(60, 60, 60), font=mid)
    cells = [f"{a}={key[a]}" for a in SUBST_ALPHA]
    for li, line in enumerate([" ".join(cells[i:i + 8]) for i in range(0, len(cells), 8)]):
        draw.text((40, 470 + li * 24), line, fill=(80, 80, 80), font=small)
    img.save(out, "PNG")
    # ключ — в комментарий файла для отладки; в игре видно на картинке
    print(f"  {out.name}  ←  подстановка «{line2}» (ciphered: «{c2}») · seed=11")
    return out


def make_n3_page2() -> Path:
    """Цезарь: «СВЕТ» → сдвинутое слово + указание смещения."""
    out = OUT_DIR / "n3_page2.png"
    plain = "СВЕТ"
    shift = 7
    cipher = "".join(
        SUBST_ALPHA[(SUBST_ALPHA.index(ch) + shift) % 32] for ch in plain
    )
    W, H = 980, 320
    img = Image.new("RGB", (W, H), (235, 220, 200))
    draw = ImageDraw.Draw(img)
    fp = _font_path()
    big = ImageFont.truetype(fp, 84) if fp else ImageFont.load_default()
    mid = ImageFont.truetype(fp, 36) if fp else ImageFont.load_default()
    small = ImageFont.truetype(fp, 22) if fp else ImageFont.load_default()

    draw.text((40, 20), "ДНЕВНИК · стр. 12", fill=(80, 60, 30), font=mid)
    draw.text((40, 80), cipher, fill=(20, 20, 60), font=big)
    draw.text((40, 220),
              f"Каждая буква смещена вперёд на +{shift} по 32-буквенному алфавиту БЕЗ Ё.",
              fill=(60, 60, 60), font=small)
    img.save(out, "PNG")
    print(f"  {out.name}  ←  Цезарь +{shift} «{plain}» → «{cipher}»")
    return out


# ========================================================================== N4 (видео)
def make_n4_placeholder() -> Path:
    """Маленький mp4-плейсхолдер. Заменишь на свою прогулку того же имени."""
    out = OUT_DIR / "n4_walk.mp4"
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = None

    if ffmpeg_exe:
        import subprocess
        cmd = [
            ffmpeg_exe, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=640x360:d=5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(out),
        ]
        try:
            subprocess.run(cmd, check=True, timeout=30)
            print(f"  {out.name}  ← 5-сек плейсхолдер mp4 (заменишь своей прогулкой)")
            return out
        except Exception as e:
            print(f"  {out.name}  ⚠ ffmpeg-плейсхолдер не собрался: {e}")

    out.write_bytes(b"PLACEHOLDER\nReplace this file with your 3-5 minute "
                    b"Moscow walking video.\nName it n4_walk.mp4\n")
    print(f"  {out.name}  ← bytes-only stub (замени на свой mp4)")
    return out


# ========================================================================== N5
def make_n5_table() -> Path:
    """Таблица ЧАСЫ / МИНУТЫ / СЕКУНДЫ → 55.7333, 37.5833 (Лужники).

    Строка 1: ЧАСЫ=44, МИНУТЫ=00  → широта 55. + 44·60/3600 = 55.7333.
    Строка 2: ЧАСЫ=35, СЕКУНДЫ=00 → долгота 37. + 35·60/3600 = 37.5833.
    """
    out = OUT_DIR / "n5_table.png"
    rows = [("44", "00", "00"), ("35", "00", "00")]

    W, H = 980, 380
    img = Image.new("RGB", (W, H), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    fp = _font_path()
    big = ImageFont.truetype(fp, 60) if fp else ImageFont.load_default()
    mid = ImageFont.truetype(fp, 38) if fp else ImageFont.load_default()
    small = ImageFont.truetype(fp, 22) if fp else ImageFont.load_default()

    draw.text((40, 24), "ЦИФРОВАЯ ТЕНЬ", fill=(60, 60, 60), font=mid)
    headers = ("ЧАСЫ", "МИНУТЫ", "СЕКУНДЫ")
    cols_x = (200, 460, 740)
    for ci, h in enumerate(headers):
        draw.text((cols_x[ci], 100), h, fill=(80, 80, 80), font=mid)
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            draw.text((cols_x[ci], 160 + ri * 90), val, fill=(20, 20, 60), font=big)

    draw.text((40, 340),
              "ШИРОТА  = 55. + (ЧАСЫ·60 + МИНУТЫ) / 3600\n"
              "ДОЛГОТА = 37. + (ЧАСЫ₂·60 + СЕКУНДЫ₂) / 3600   ← из 2-й строки",
              fill=(60, 60, 60), font=small)
    img.save(out, "PNG")
    print(f"  {out.name}  ← 44·60=2640/3600=0.7333 → 55.7333 / 35·60=2100/3600=0.5833 → 37.5833")
    return out


# ========================================================================== N6
def make_n6_cipher() -> Path:
    """A1Z26 → 23-08-11-24 (что эквивалентно ЦЗКЧ → Caesar +5 → СВЕТ)."""
    out = OUT_DIR / "n6_cipher.png"
    enc = "23-08-11-24"
    W, H = 980, 360
    img = Image.new("RGB", (W, H), (244, 241, 230))
    draw = ImageDraw.Draw(img)
    fp = _font_path()
    big = ImageFont.truetype(fp, 84) if fp else ImageFont.load_default()
    mid = ImageFont.truetype(fp, 32) if fp else ImageFont.load_default()
    small = ImageFont.truetype(fp, 22) if fp else ImageFont.load_default()

    draw.text((40, 30), "КОД · A1Z26 + ЦЕЗАРЬ", fill=(80, 60, 30), font=mid)
    draw.text((40, 100), enc, fill=(20, 20, 60), font=big)
    draw.text((40, 220),
              "Шаг 1: 32-буквенный русский алфавит БЕЗ Ё (А=1, Б=2, …, Я=32).\n"
              "Шаг 2: каждая полученная буква смещена на +5 по тому же алфавиту\n"
              "(отмени: сдвинь на −5).",
              fill=(60, 60, 60), font=small)
    img.save(out, "PNG")
    print(f"  {out.name}  ← {enc} → ЦЗКЧ → СВЕТ")
    return out


# ========================================================================== README
ASSET_NOTES = """\
# Ассеты для ARG «Аргус-1001»

Эти файлы — медиа для стадий квеста, на которые ссылается stages.yaml.

| файл                  | стадия          | описание                                            |
| --------------------- | --------------- | --------------------------------------------------- |
| n1_clue.jpg           | N1_intro, N1_*  | фото Воробьёвых гор с EXIF GPS                      |
| n2_audio1.wav         | N2_audio1       | «АРГУС» в спектрограмме                             |
| n2_audio2.wav         | N2_audio2       | «СЛЕД» в спектрограмме                              |
| n3_page1.png          | N3_intro        | страница дневника (подстановка → «ИЩИ»)              |
| n3_page2.png          | N3_page2        | страница с Цезарем  → «СВЕТ»                        |
| n4_walk.mp4           | N4_video        | твоя видео-прогулка по Москве (3–5 мин)             |
| n5_table.png          | N5_intro        | таблица ЧАСЫ/МИНУТЫ/СЕКУНДЫ → координаты            |
| n6_cipher.png         | N6_intro        | A1Z26 (23-08-11-24) → Цезарь -5 → «СВЕТ»            |

## Перегенерация

```bash
python3 tools/make_quest_assets.py   # заменяет все файлы кроме .gitkeep
```

## Видео (n4_walk.mp4)

Файл по умолчанию — 5-секундный mp4-плейсхолдер. Запиши свою прогулку
по Москве (3–5 мин, в кадре несколько объектов: вывески, стены, асфальт),
сохрани **с тем же именем** — stages.yaml уже ссылается на него.

В одном из кадров запиши/приклей надпись `СВЕТ` (красным или жёлтым,
крупно, на 1–2 секунды). Это и есть ответ узла N4.

## QR-коды для локаций

```bash
python3 bot/make_qr.py   # генерит bot/qr/<stage_id>.png
```

QR-стадии в квесте: N1_qr (ARGUS-WATCH) и N5_qr (ARGUS-LUZHNIKI). Распечатай
и спрячь на местах: смотровая Воробьёвых гор и опора освещения в Лужниках.

## Бот

`entry_code` в `bot/quest/stages.yaml` сейчас `ARGUS1001`.
Шифруется в START.txt внутри zengame.siq (см. `tools/build_v5.py:quest_start_text`).
"""


def write_readme() -> None:
    out = OUT_DIR / "README.md"
    out.write_text(ASSET_NOTES, encoding="utf-8")
    print(f"  README.md")


# ========================================================================== main
def main():
    print("Генерация ассетов для ARG «Аргус-1001» →", OUT_DIR)
    print("-" * 60)
    make_n1_clue()
    make_word_spectrogram_wav("АРГУС", OUT_DIR / "n2_audio1.wav", duration=4.0)
    make_word_spectrogram_wav("СЛЕД", OUT_DIR / "n2_audio2.wav", duration=3.0)
    make_n3_page1()
    make_n3_page2()
    make_n4_placeholder()
    make_n5_table()
    make_n6_cipher()
    write_readme()
    print("-" * 60)
    print("Готово.")


if __name__ == "__main__":
    main()
