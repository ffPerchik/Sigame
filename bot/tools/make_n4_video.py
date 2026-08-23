#!/usr/bin/env python3
"""N4 «НАБЛЮДЕНИЕ»: пост-обработка сток-клипа в «архив камеры CAM-3».

Вход: реальная ночная улица (бот/quest/source/*.mp4). Выход:
  artifact_4a.mp4 — CCTV-запись: REC/таймкод, вспышка-кадр с hex(ШУМ),
                    финальная «метка» с QR (deep-link CAM3EYE).
  artifact_4b.png — стоп-кадр метки (запасной артефакт).
  artifact_4c.png — стоп-кадр вспышки (запасной артефакт).

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

W, H = 1920, 1080          # итог: апскейл до 1080p (QR должен пережить YouTube)
FLASH_AT = 0.55            # доля ролика, где вспышка
FLASH_LEN = 12             # кадров (~0.5 c при 25 fps)
MARK_SECS = 4.0            # сколько секунд в конце видна метка
HEX_WORD = " ".join(f"{b:02x}" for b in "ШУМ".encode("utf-8"))  # d0a8 d0a3 d09c
QR_CODE = "CAM3EYE"


def ffmpeg() -> str | None:
    for candidate in (shutil.which("ffmpeg"),):
        if candidate:
            return candidate
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    key = (name, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(str(FONTS / name), size)
    return _FONT_CACHE[key]


_FONT_CACHE: dict = {}


def run_ff(args: list[str]) -> None:
    exe = ffmpeg()
    if not exe:
        sys.exit("ffmpeg не найден (установи imageio-ffmpeg)")
    subprocess.run([exe, "-hide_banner", "-loglevel", "error", *args], check=True)


def make_qr(bot_name: str) -> Image.Image:
    url = f"https://t.me/{bot_name}?start={QR_CODE}"
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    print(f"  QR ← {url}")
    return img


def hud(img: Image.Image, idx: int, fps: int) -> None:
    """CCTV-оверлей: REC, камера, таймкод, лёгкая обесцвеченность."""
    d = ImageDraw.Draw(img, "RGBA")
    total = idx / fps
    hh, mm, ss = 22, 41, 7 + int(total)
    ff = int((total % 1) * fps)
    ts = f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"

    # REC ●
    d.ellipse((52, 48, 78, 74), fill=(220, 40, 40))
    d.text((96, 46), "REC", fill=(240, 240, 240), font=font("DejaVuSansMono-Bold.ttf", 40))
    cam = "CAM-3 · SECTOR 4 · ARGVS"
    tw = d.textlength(cam, font=font("DejaVuSansMono-Bold.ttf", 32))
    d.text((W - 56 - tw, 50), cam, fill=(240, 240, 240), font=font("DejaVuSansMono-Bold.ttf", 32))
    tw = d.textlength(ts, font=font("DejaVuSansMono-Bold.ttf", 36))
    d.text((W - 56 - tw, H - 78), ts, fill=(230, 230, 230), font=font("DejaVuSansMono-Bold.ttf", 36))


def flash_frame(idx: int) -> Image.Image:
    img = Image.new("RGB", (W, H), (6, 6, 8))
    d = ImageDraw.Draw(img)
    # глитч-полосы
    rng = np.random.default_rng(1000 + idx)
    for y in rng.integers(0, H, 26):
        x0 = int(rng.integers(0, W // 2))
        ln = int(rng.integers(120, 700))
        d.rectangle((x0, int(y), x0 + ln, int(y) + int(rng.integers(2, 6))),
                    fill=(70, 70, 80))
    d.text(((W - ImageFont.truetype(str(FONTS / "DejaVuSansMono-Bold.ttf"), 96).getlength(HEX_WORD)) // 2, 460),
           HEX_WORD, fill=(235, 235, 235), font=font("DejaVuSansMono-Bold.ttf", 96))
    d.text((W // 2 - 60, 600), "UTF-8", fill=(120, 120, 120), font=font("DejaVuSansMono-Bold.ttf", 44))
    return img


def mark_overlay(base: Image.Image, qr: Image.Image, alpha: float) -> None:
    """Плакат-метка с QR поверх затемнённого кадра."""
    if alpha <= 0:
        return
    if alpha < 1:
        dark = ImageEnhance.Brightness(base).enhance(0.55 + 0.45 * (1 - alpha))
        base.paste(dark, (0, 0))
    else:
        base.paste(ImageEnhance.Brightness(base).enhance(0.5), (0, 0))

    pw, ph = 720, 950
    px, py = (W - pw) // 2 + 210, (H - ph) // 2
    poster = Image.new("RGBA", (pw, ph), (245, 245, 245, 255))
    pd = ImageDraw.Draw(poster)
    pd.rectangle((0, 0, pw - 1, 96), fill=(160, 30, 30))
    head = "ARGVS-1001 · МЕТКА 4/6"
    pd.text(((pw - ImageFont.truetype(str(FONTS / "DejaVuSansMono-Bold.ttf"), 40).getlength(head)) // 2, 28),
            head, fill=(245, 245, 245), font=font("DejaVuSansMono-Bold.ttf", 40))
    qr_s = qr.resize((560, 560), Image.NEAREST)
    poster.paste(qr_s, ((pw - 560) // 2, 150))
    pd.text(((pw - ImageFont.truetype(str(FONTS / "DejaVuSansMono-Bold.ttf"), 36).getlength("СКАН С ЭКРАНА")) // 2, ph - 140),
            "СКАН С ЭКРАНА", fill=(20, 20, 20), font=font("DejaVuSansMono-Bold.ttf", 36))
    pd.text(((pw - ImageFont.truetype(str(FONTS / "DejaVuSansMono-Bold.ttf"), 30).getlength("CAM-3")) // 2, ph - 80),
            "CAM-3", fill=(120, 120, 120), font=font("DejaVuSansMono-Bold.ttf", 30))
    pd.rectangle((0, 0, pw - 1, ph - 1), outline=(20, 20, 20), width=6)

    if alpha < 1:
        poster.putalpha(int(255 * alpha))
    base.paste(poster, (px, py), poster)

    # прицельные уголки кадра
    d = ImageDraw.Draw(base, "RGBA")
    L, c = 70, (220, 60, 60, int(255 * min(1, alpha + 0.2)))
    for cx, cy, dx, dy in ((56, 56, 1, 1), (W - 56, 56, -1, 1), (56, H - 56, 1, -1), (W - 56, H - 56, -1, -1)):
        d.line((cx, cy, cx + dx * L, cy), fill=c, width=6)
        d.line((cx, cy, cx, cy + dy * L), fill=c, width=6)


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

    qr = make_qr(args.bot_name)

    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        raw, out_frames = tdir / "raw", tdir / "out"
        raw.mkdir()
        out_frames.mkdir()
        # 1) кадры из исходника
        run_ff(["-i", str(src), "-vf", f"scale={W}:{H}:flags=lanczos", str(raw / "f%04d.png")])
        frames = sorted(raw.glob("f*.png"))
        n, fps = len(frames), 25
        print(f"  кадров: {n} ({n / fps:.1f} c)")

        flash_i = int(n * FLASH_AT)
        mark_from = n - int(MARK_SECS * fps)

        for i, fp in enumerate(frames):
            if flash_i <= i < flash_i + FLASH_LEN:
                img = flash_frame(i)
            else:
                img = Image.open(fp).convert("RGB")
                img = ImageEnhance.Color(img).enhance(0.72)
                hud(img, i, fps)
                if i >= mark_from:
                    t = (i - mark_from) / fps
                    mark_overlay(img, qr, min(1.0, t / 0.4))
            img.save(out_frames / f"f{i:04d}.png")

        # 2) mp4
        run_ff(["-y", "-framerate", str(fps), "-i", str(out_frames / "f%04d.png"),
                "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
                str(IMAGES / "artifact_4a.mp4")])

        # 3) запасные стоп-кадры
        Image.open(out_frames / f"f{mark_from + int(0.5 * fps):04d}.png").save(
            IMAGES / "artifact_4b.png", optimize=True)
        Image.open(out_frames / f"f{flash_i:04d}.png").save(
            IMAGES / "artifact_4c.png", optimize=True)

    print(f"  N4 видео: artifact_4a.mp4  вспышка@{flash_i} ({HEX_WORD} = ШУМ), QR-код {QR_CODE}")
    print(f"  метка последние {MARK_SECS} c; стоп-кадры: artifact_4b.png, artifact_4c.png")


if __name__ == "__main__":
    main()
