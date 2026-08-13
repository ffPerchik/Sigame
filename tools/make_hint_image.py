#!/usr/bin/env python3
"""Генерирует картинку-подсказку квеста (content/Images/quest_hint.jpg).
Тёмная атмосферная карточка с загадкой, ведущей к переименованию .siq в .zip."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import random

OUT = Path(__file__).resolve().parent.parent / "content" / "Images" / "quest_hint.jpg"
W, H = 1280, 860
BG = (10, 12, 20)
INK = (230, 236, 245)
ACCENT = (94, 234, 212)      # cyan
DIM = (120, 134, 160)
AMBER = (235, 180, 80)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img, "RGBA")

# --- фон: мягкое свечение по центру + виньетка ---
for r, a in [(900, 14), (600, 10), (320, 8)]:
    d.ellipse([W//2-r, H//2-r, W//2+r, H//2+r], fill=(40, 70, 90, a))
# лёгкий «цифровой» шум-точки
random.seed(7)
for _ in range(900):
    x, y = random.randint(0, W), random.randint(0, H)
    d.point((x, y), fill=(255, 255, 255, random.randint(4, 16)))

# --- мотив: концентрические круги + «глаз» (намёк на «смотри внимательнее») ---
cx, cy = W//2, 250
for r, a in [(150, 30), (120, 50), (90, 80), (60, 120)]:
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(*ACCENT, a), width=2)
d.ellipse([cx-26, cy-26, cx+26, cy+26], fill=(*AMBER, 220))
d.ellipse([cx-10, cy-10, cx+10, cy+10], fill=BG)
# «зрачок» сверху
img = img.filter(ImageFilter.GaussianBlur(0.4))
d = ImageDraw.Draw(img, "RGBA")

F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
f_title = ImageFont.truetype(FB, 58)
f_body = ImageFont.truetype(F, 36)
f_mono = ImageFont.truetype(F, 26)
f_small = ImageFont.truetype(F, 24)


def center(text, y, font, fill, letter_spacing=0):
    bbox = d.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    d.text(((W - w) / 2, y), text, font=font, fill=fill)


# --- угловые метки ---
cl = 40
for (x, y) in [(40, 40), (W-40, 40), (40, H-40), (W-40, H-40)]:
    d.line([x-cl, y, x+cl, y], fill=(*ACCENT, 90), width=2)
    d.line([x, y-cl, x, y+cl], fill=(*ACCENT, 90), width=2)

# --- текст ---
center("П О С Л А Н И Е", 420, f_title, ACCENT)
center("из-под обёртки файла", 492, f_body, DIM)

lines = [
    "Файл, который вы только что проиграли,",
    "хранит то, чего нет на экране.",
    "",
    "Его расширение  .SIQ  — на деле это  ZIP.",
    "Смени  .SIQ  на  .ZIP,  распакуй",
    "и найди спрятанный старт.",
]
y = 580
for ln in lines:
    center(ln, y, f_body, INK)
    y += 50

center("⌄  ключ к квесту — внутри  ⌄", y + 24, f_small, AMBER)

img.save(OUT, "JPEG", quality=90, optimize=True)
print("saved", OUT, OUT.stat().st_size, "bytes")
