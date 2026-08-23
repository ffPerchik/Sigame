#!/usr/bin/env python3
"""N4 «НАБЛЮДЕНИЕ»: пост-обработка сток-клипа в «архив камеры CAM-3».

Слои (4 загадки):
  1. Два глитч-кадра с половинами hex(ШУМ): d0 a8 d0 / a3 d0 9c.
  2. Шесть коротких кадров по одной букве (В З Г Л Я Д, хронологически).
  3. Описание YouTube: LOG 0C 06 0E 08 01 → hex → A1Z26 → ЛИНЗА.
  4. Метки: фальшивый QR (CAM3TRAP, сканируется сразу — ловушка) в середине
     и настоящий отзеркаленный QR (CAM3EYE) в конце.

Выход: artifact_4a.mp4, artifact_4b.png (стоп-кадр метки), artifact_4c.png (глитч).

  python3 bot/tools/make_n4_video.py [--input путь.mp4] [--bot-name NAME]
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

try:
    import qrcode
except ImportError:
    print("Нужен пакет qrcode: pip install qrcode")
    raise

BOT_DIR = Path(__file__).resolve().parent.parent
IMAGES = BOT_DIR / "quest" / "images"
FONTS = BOT_DIR / "tools" / "fonts"

W, H = 1920, 1080
FPS = 25
# Хронология строго последовательна: hex-сбои → буквенные сбои → ловушка → метка.
FLASH1_AT = 0.27           # доля ролика: первый глитч-кадр (d0 a8 d0)
FLASH2_AT = 0.43           # второй глитч-кадр (a3 d0 9c)
FLASH_LEN = 12             # кадров (~0.5 c)
LETTERS = "ВЗГЛЯД"
LETTER_AT = [0.50, 0.545, 0.59, 0.635, 0.68, 0.725]  # буквенные сбои, после hex
LETTER_LEN = 3             # кадров (~0.12 c)
TRAP_AT, TRAP_LEN = 0.76, 30   # фальшивая метка (~1.2 c)
MARK_SECS = 4.0            # настоящая метка в конце
QR_CODE = "CAM3EYE"
TRAP_CODE = "CAM3TRAP"
HEX1, HEX2 = "d0 a8 d0", "a3 d0 9c"


def ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def run_ff(args: list[str]) -> None:
    exe = ffmpeg()
    if not exe:
        sys.exit("ffmpeg не найден (установи imageio-ffmpeg)")
    subprocess.run([exe, "-hide_banner", "-loglevel", "error", *args], check=True)


_FONT_CACHE: dict = {}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    key = (name, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(str(FONTS / name), size)
    return _FONT_CACHE[key]


def mono(size: int) -> ImageFont.FreeTypeFont:
    return font("DejaVuSansMono-Bold.ttf", size)


def make_qr(text: str) -> Image.Image:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def hud(img: Image.Image, idx: int) -> None:
    d = ImageDraw.Draw(img, "RGBA")
    total = idx / FPS
    hh, mm, ss = 22, 41, 7 + int(total)
    ff = int((total % 1) * FPS)
    ts = f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"
    d.ellipse((52, 48, 78, 74), fill=(220, 40, 40))
    d.text((96, 46), "REC", fill=(240, 240, 240), font=mono(40))
    cam = "CAM-3 · SECTOR 4 · ARGVS"
    d.text((W - 56 - d.textlength(cam, font=mono(32)), 50), cam,
           fill=(240, 240, 240), font=mono(32))
    d.text((W - 56 - d.textlength(ts, font=mono(36)), H - 78), ts,
           fill=(230, 230, 230), font=mono(36))


def flash_frame(idx: int, hex_text: str) -> Image.Image:
    img = Image.new("RGB", (W, H), (6, 6, 8))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(1000 + idx)
    for y in rng.integers(0, H, 26):
        x0, ln = int(rng.integers(0, W // 2)), int(rng.integers(120, 700))
        d.rectangle((x0, int(y), x0 + ln, int(y) + int(rng.integers(2, 6))), fill=(70, 70, 80))
    d.text(((W - mono(96).getlength(hex_text)) // 2, 460), hex_text,
           fill=(235, 235, 235), font=mono(96))
    d.text((W // 2 - 60, 600), "UTF-8", fill=(120, 120, 120), font=mono(44))
    return img


def letter_frame(idx: int, letter: str) -> Image.Image:
    """Буквенный сбой: тот же тёмный глитч-стиль, но с крупной буквой."""
    img = flash_frame(idx, "")
    d = ImageDraw.Draw(img)
    d.text(((W - mono(220).getlength(letter)) // 2, (H - 220) // 2 - 40), letter,
           fill=(240, 240, 240), font=mono(220))
    return img


def poster(qr_img: Image.Image, header: str) -> Image.Image:
    pw, ph = 720, 950
    p = Image.new("RGB", (pw, ph), (245, 245, 245))
    pd = ImageDraw.Draw(p)
    pd.rectangle((0, 0, pw - 1, 96), fill=(160, 30, 30))
    pd.text(((pw - mono(40).getlength(header)) // 2, 28), header,
            fill=(245, 245, 245), font=mono(40))
    p.paste(qr_img.resize((560, 560), Image.NEAREST), ((pw - 560) // 2, 150))
    pd.text(((pw - mono(36).getlength("СКАН С ЭКРАНА")) // 2, ph - 140),
            "СКАН С ЭКРАНА", fill=(20, 20, 20), font=mono(36))
    pd.text(((pw - mono(30).getlength("CAM-3")) // 2, ph - 80),
            "CAM-3", fill=(120, 120, 120), font=mono(30))
    pd.rectangle((0, 0, pw - 1, ph - 1), outline=(20, 20, 20), width=6)
    return p


def paste_poster(base: Image.Image, p: Image.Image, alpha: float) -> None:
    px, py = (W - p.width) // 2 + 210, (H - p.height) // 2
    if alpha < 1:
        alpha_img = Image.new("L", p.size, int(255 * alpha))
        base.paste(p.convert("RGBA"), (px, py), alpha_img)
    else:
        base.paste(p, (px, py))
    d = ImageDraw.Draw(base, "RGBA")
    L, c = 70, (220, 60, 60, int(255 * min(1, alpha + 0.2)))
    for cx, cy, dx, dy in ((56, 56, 1, 1), (W - 56, 56, -1, 1), (56, H - 56, 1, -1), (W - 56, H - 56, -1, -1)):
        d.line((cx, cy, cx + dx * L, cy), fill=c, width=6)
        d.line((cx, cy, cx, cy + dy * L), fill=c, width=6)


def dim(base: Image.Image, alpha: float, k: float = 0.55) -> None:
    """Плавное затемнение до доли k (alpha=1 → полностью затемнён)."""
    base.paste(ImageEnhance.Brightness(base).enhance(1 - k * alpha), (0, 0))


def main() -> None:
    ap = argparse.ArgumentParser()
    default_in = BOT_DIR / "quest" / "source" / "mixkit-quiet-tokyo-street-at-night-4451-hd-ready.mp4"
    ap.add_argument("--input", default=str(default_in))
    ap.add_argument("--bot-name", default=os.environ.get("BOT_USERNAME", "your_bot"))
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        sys.exit(f"нет исходника: {src}")
    print(f"N4: исходник {src.name}")

    real_qr = make_qr(f"https://t.me/{args.bot_name}?start={QR_CODE}")
    trap_qr = make_qr(f"https://t.me/{args.bot_name}?start={TRAP_CODE}")
    real_poster = poster(real_qr, "ARGVS-1001 · МЕТКА 4/6")          # зеркалим при вставке
    trap_poster = poster(trap_qr, "ARGVS-1001 · МЕТКА 4/6")          # ловушка — как настоящая
    print(f"  QR ← {args.bot_name}?start={QR_CODE} (зеркальный) и ловушка {TRAP_CODE}")

    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        raw, out_frames = tdir / "raw", tdir / "out"
        raw.mkdir()
        out_frames.mkdir()
        run_ff(["-i", str(src), "-vf", f"scale={W}:{H}:flags=lanczos", str(raw / "f%04d.png")])
        frames = sorted(raw.glob("f*.png"))
        n = len(frames)
        print(f"  кадров: {n} ({n / FPS:.1f} c)")

        f1 = int(n * FLASH1_AT)
        f2 = int(n * FLASH2_AT)
        letter_i = [int(n * x) for x in LETTER_AT]
        trap_i = int(n * TRAP_AT)
        mark_from = n - int(MARK_SECS * FPS)

        for i, fp in enumerate(frames):
            letter_hit = next(
                (k for k, start in enumerate(letter_i)
                 if start <= i < start + LETTER_LEN), None)
            if f1 <= i < f1 + FLASH_LEN:
                img = flash_frame(i, HEX1)
            elif f2 <= i < f2 + FLASH_LEN:
                img = flash_frame(i, HEX2)
            elif letter_hit is not None:
                img = letter_frame(i, LETTERS[letter_hit])
            else:
                img = Image.open(fp).convert("RGB")
                img = ImageEnhance.Color(img).enhance(0.72)
                hud(img, i)
                if trap_i <= i < trap_i + TRAP_LEN:
                    t = (i - trap_i) / FPS
                    dim(img, min(1.0, t / 0.3))
                    paste_poster(img, trap_poster, alpha=min(1.0, t / 0.3))
                elif i >= mark_from:
                    t = (i - mark_from) / FPS
                    dim(img, min(1.0, t / 0.4))
                    paste_poster(img, real_poster.transpose(Image.FLIP_LEFT_RIGHT),
                                 alpha=min(1.0, t / 0.4))
            img.save(out_frames / f"f{i:04d}.png")

        run_ff(["-y", "-framerate", str(FPS), "-i", str(out_frames / "f%04d.png"),
                "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
                str(IMAGES / "artifact_4a.mp4")])

        Image.open(out_frames / f"f{mark_from + int(0.6 * FPS):04d}.png").save(
            IMAGES / "artifact_4b.png", optimize=True)
        Image.open(out_frames / f"f{f1:04d}.png").save(
            IMAGES / "artifact_4c.png", optimize=True)

    print(f"  глитчи: @{f1} «{HEX1}» и @{f2} «{HEX2}» → ШУМ")
    print(f"  буквы-сбои {LETTERS} на кадрах {letter_i}")
    print(f"  ловушка {TRAP_CODE} @{trap_i}; метка (зеркало) последние {MARK_SECS} c")


if __name__ == "__main__":
    main()
