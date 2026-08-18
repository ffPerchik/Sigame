#!/usr/bin/env python3
"""Генератор тизера ARG «Аргус-1001» — атмосферный постер, без ответов.

Антураж: тёмная типографика + неоновый акцент, шумоподобный фон,
«глифчатые» карточки узлов (название узла + крипто-намёк).
Все методы, ответы и фрагменты спрятаны.

Запуск:
    python3 tools/make_quest_teaser.py
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "doc"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---- палитра --------------------------------------------------------------
BG          = (8, 12, 22)
PANEL       = (14, 20, 36)
EDGE        = (40, 50, 78)
GOLD        = (228, 172, 50)
GOLD_SOFT   = (138, 96, 22)
GREEN       = (110, 220, 96)
RED         = (220, 70, 80)
PALE        = (218, 224, 240)
DIM         = (108, 122, 152)
GRID_GREEN  = (28, 60, 48)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def f(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    p = FONT_BOLD if (bold and Path(FONT_BOLD).exists()) else FONT_REG
    if Path(p).exists():
        return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def speckle_bg(w: int, h: int, density: float = 0.0015) -> Image.Image:
    """Тёмный фон с лёгким шумом (как старая плёнка)."""
    img = Image.new("RGB", (w, h), BG)
    px = img.load()
    n = int(w * h * density)
    for _ in range(n):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        v = random.choice([(20, 30, 50), (40, 56, 90), (12, 18, 32)])
        px[x, y] = v
    # Подкрась парой красных «горящих» пикселей
    for _ in range(int(n / 20)):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        px[x, y] = (160, 36, 44)
    return img


def add_grid(draw: ImageDraw.ImageDraw, w: int, h: int, step: int = 60, color=GRID_GREEN):
    for x in range(0, w, step):
        draw.line([(x, 0), (x, h)], fill=color, width=1)
    for y in range(0, h, step):
        draw.line([(0, y), (w, y)], fill=color, width=1)


def draw_central_emblem(draw, cx, cy, color=GOLD):
    r_outer = 150
    for r, col in ((r_outer, color), (r_outer - 16, GOLD_SOFT), (r_outer - 32, color)):
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=2)
    inner_r = 88
    draw.ellipse((cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r),
                 fill=PANEL, outline=color, width=3)
    for i in range(12):
        a = -math.pi / 2 + i * (2 * math.pi / 12)
        rr = r_outer - 8
        x = cx + rr * math.cos(a)
        y = cy + rr * math.sin(a)
        s = 7 if i % 3 == 0 else 4
        col = color if i % 3 == 0 else GREEN
        draw.ellipse((x - s, y - s, x + s, y + s), fill=col)
    big  = f(46, bold=True)
    small = f(22, bold=False)
    t1 = "ARGVS"
    t2 = "1 0 0 1"
    w1, h1 = text_size(draw, t1, big)
    w2, h2 = text_size(draw, t2, small)
    draw.text((cx - w1 / 2, cy - h1 / 2 - 6), t1, fill=color, font=big)
    draw.text((cx - w2 / 2, cy + h1 / 2 - h2 / 2 + 4), t2, fill=GREEN, font=small)


def draw_glitch_horizontal(draw, x0, x1, y, color=GREEN, width=1, segments=3):
    """Случайная «оборванная» линия — даёт poster-вайб."""
    span = x1 - x0
    seg = max(span // segments, 1)
    i = 0
    while i < segments:
        take = seg if i % 2 == 0 else seg - random.randint(0, seg // 3)
        take = max(0, take)
        draw.line([(x0 + i * seg, y), (x0 + i * seg + take, y)], fill=color, width=width)
        i += 1


NODE_TEASER = [
    ("01", "СНИМОК",
        "один кадр хранит координаты"),
    ("02", "СПЕКТР",
        "голос, который можно увидеть"),
    ("03", "ДНЕВНИК",
        "страницы, которые не открыть глазами"),
    ("04", "МАРШРУТ",
        "кадры, в которых есть лишнее"),
    ("05", "ЧИСЛА",
        "не время. не цены. только координаты"),
    ("06", "КОД",
        "одна строка — три замка"),
]


def draw_node_card(draw, cx, cy, num, name, cryptic, color):
    """«Глифчатая» карточка-намёк, без ответа и метода."""
    box_w, box_h = 360, 200
    x0, y0 = cx - box_w / 2, cy - box_h / 2
    x1, y1 = cx + box_w / 2, cy + box_h / 2

    # тень
    draw.rounded_rectangle((x0 + 6, y0 + 8, x1 + 6, y1 + 8),
                           radius=14, fill=(0, 0, 0))
    # карточка
    draw.rounded_rectangle((x0, y0, x1, y1), 14, fill=PANEL, outline=color, width=2)

    # угловые «скобки» (постерная ржавчина)
    csz = 22
    for cx0, cy0, dx, dy in [(x0, y0, 1, 1), (x1, y0, -1, 1),
                             (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        draw.line([(cx0, cy0 + dy * csz), (cx0, cy0), (cx0 + dx * csz, cy0)],
                  fill=color, width=2)

    # номер в стиле «капча-зачёркивание»
    fb = f(48, bold=True)
    nw, nh = text_size(draw, num, fb)
    draw.text((x0 + 20, y0 + 14), num, fill=color, font=fb)
    # замазанный прямоугольник-засветка поверх номера
    draw.rectangle((x0 + 18, y0 + 14, x0 + 20 + nw, y0 + 14 + nh),
                   fill=PANEL, outline=color, width=2)
    draw.text((x0 + 20, y0 + 14), num, fill=color, font=fb)

    # название узла
    fn = f(26, bold=True)
    n_w, _ = text_size(draw, name, fn)
    fnt_x = cx - n_w / 2
    fnt_y = y0 + 90
    draw.text((fnt_x, fnt_y), name, fill=PALE, font=fn)
    # линия под именем
    draw.line([(fnt_x, fnt_y + 36), (fnt_x + n_w, fnt_y + 36)], fill=color, width=2)

    # криптический намёк (мелкий курсив-эквивалент)
    fs = f(15)
    # выравнивание по центру
    lines = []
    cur = ""
    sw = text_size(draw, "0000 0000 0000 0000", fs)[0]
    for word in cryptic.split():
        cand = (cur + " " + word).strip()
        if text_size(draw, cand, fs)[0] > box_w - 60:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    for i, line in enumerate(lines):
        lw, _ = text_size(draw, line, fs)
        draw.text((cx - lw / 2, fnt_y + 46 + i * 22), line, fill=DIM, font=fs)

    # засекреченный «замо́к»: ? символ над правым углом
    fl = f(36, bold=True)
    draw.text((x1 - 50, y0 - 8), "? ?", fill=GOLD, font=fl)


def render(out_path: Path) -> None:
    W, H = 1900, 1420
    img = speckle_bg(W, H, density=0.0008)   # фон: тёмный шум
    draw = ImageDraw.Draw(img)

    # сетка-«линии передачи»
    add_grid(draw, W, H, step=72, color=GRID_GREEN)

    # крест-накрест лёгкие «трансляционные» линии
    for y in range(120, H - 100, 48):
        draw.line([(0, y), (W, y + 6)], fill=(20, 30, 50), width=1)

    # === TITLE ===
    fb = f(78, bold=True)
    big = "ARGVS · 1001"
    bw, bh = text_size(draw, big, fb)
    draw.text(((W - bw) / 2, 70), big, fill=GOLD, font=fb)

    # подзаголовок
    sub = f(22)
    s = "АНОНИМНЫЙ СИГНАЛ  ·  ШЕСТЬ ЗАШИТЫХ УЗЛОВ  ·  МОСКВА, БЛИЖАЙШИЕ ДНИ"
    sw, _ = text_size(draw, s, sub)
    draw.text(((W - sw) / 2, 158), s, fill=GREEN, font=sub)

    # лёгкие «вертикальные» декор-линии
    draw.line([(120, 200), (120, H - 130)], fill=EDGE, width=1)
    draw.line([(W - 120, 200), (W - 120, H - 130)], fill=EDGE, width=1)

    # === центральная печать ===
    cx, cy = W / 2, H / 2 + 20
    draw_central_emblem(draw, int(cx), int(cy))

    # над печатью: «НОМЕР СЕАНСА · 0001» — мелкой готической меткой
    sidemark = f(13, bold=True)
    side = СЕАНС if False else "SESSION · OPEN"   # noqa: keep literal
    sw2, _ = text_size(draw, side, sidemark)
    draw.text(((W - sw2) / 2, cy - 220), side, fill=DIM, font=sidemark)

    # под печатью: одна строка — «получено в эфире»
    rx = f(13)
    rec = "░ ПРИНЯТО ИЗ ЭФИРА ░    ── ARGV-NET ──    ░ СЕАНС #1 ░"
    rw, _ = text_size(draw, rec, rx)
    draw.text(((W - rw) / 2, cy + 95), rec, fill=GOLD_SOFT, font=rx)
    rec2 = "шифрование · декодирование · анализ"
    r2w, _ = text_size(draw, rec2, rx)
    draw.text(((W - r2w) / 2, cy + 116), rec2, fill=DIM, font=rx)

    # === 6 узлов вокруг печати ===
    RY, RX = 410, 700
    positions = []
    for i in range(6):
        a = -math.pi / 2 + i * (2 * math.pi / 6)
        positions.append((cx + RX * math.cos(a), cy + RY * math.sin(a)))

    # пунктирные «лучи» центр↔узлы
    for px, py in positions:
        dx_, dy_ = px - cx, py - cy
        L = math.hypot(dx_, dy_)
        ux, uy = dx_ / L, dy_ / L
        sx = cx + ux * 150
        sy = cy + uy * 150
        ex = px - ux * 200
        ey = py - uy * 110
        # пунктир
        steps = 16
        for j in range(0, steps, 2):
            t0, t1 = j / steps, (j + 1) / steps
            draw.line([(sx + (ex - sx) * t0, sy + (ey - sy) * t0),
                       (sx + (ex - sx) * t1, sy + (ey - sy) * t1)],
                      fill=EDGE, width=1)
    # пунктир сосед-↔-сосед
    for i in range(6):
        for j in (i + 1, i + 2):
            jj = j % 6
            ai, aj = positions[i], positions[jj]
            steps = 24
            dx_, dy_ = aj[0] - ai[0], aj[1] - ai[1]
            L = math.hypot(dx_, dy_)
            for k in range(0, steps, 2):
                t0, t1 = k / steps, (k + 1) / steps
                draw.line([(ai[0] + dx_ * t0, ai[1] + dy_ * t0),
                           (ai[0] + dx_ * t1, ai[1] + dy_ * t1)],
                          fill=(36, 48, 70), width=1)

    palette = [
        (90, 160, 230),    # синий
        (220, 110, 200),   # розовый
        (240, 200, 110),   # жёлтый
        (130, 220, 96),    # зелёный
        (220, 140, 90),    # оранжевый
        (190, 130, 230),   # фиолетовый
    ]

    for (num, name, crypt), (px, py), col in zip(NODE_TEASER, positions, palette):
        draw_node_card(draw, int(px), int(py), num, name, crypt, col)

    # === БОКОВЫЕ МЕТКИ ===
    f_left = f(16)
    f_left_b = f(16, bold=True)
    items = [
        ("ПРОШЛО",     "до старта"),
        ("СЕАНС",      "не угадать — пропустить"),
        ("СЛОИ",       "заказной — нельзя выбирать"),
        ("ОТВЕТЫ",     "не записаны. нужно дойти"),
    ]
    y = 230
    for k, v in items:
        draw.text((160, y), k + ":", fill=GOLD, font=f_left_b)
        kw, _ = text_size(draw, k + ": ", f_left_b)
        draw.text((160 + kw, y), v, fill=PALE, font=f_left)
        y += 26

    # правый блок — инструменты (но без спойлеров: только «с чем играть»)
    y = 230
    items2 = [
        ("ИНСТРУМЕНТ", "ищи сам — выдадим по ходу"),
        ("УШИ",        "что-то спрятано в звуке"),
        ("ГЛАЗА",      "что-то спрятано в кадре"),
        ("МОЗГ",       "что-то спрятано в цифрах"),
    ]
    for k, v in items2:
        ks = "▸"
        draw.text((W - 480, y), ks, fill=GOLD, font=f_left_b)
        draw.text((W - 460, y), k + ":", fill=GOLD, font=f_left_b)
        kw, _ = text_size(draw, k + ": ", f_left_b)
        draw.text((W - 460 + kw, y), v, fill=PALE, font=f_left)
        y += 26

    # === НИЖНИЙ БЛОК: когда / что ===
    band_y = H - 130
    draw.rounded_rectangle((60, band_y, W - 60, H - 60), 14,
                           fill=PANEL, outline=GOLD, width=2)

    fs = f(18, bold=True)
    # Левая панель — дата
    draw.text((100, band_y + 22), "СТАРТ", fill=DIM, font=fs)
    fd = f(34, bold=True)
    draw.text((100, band_y + 44), "ВЫБЕРИ САМ", fill=GOLD, font=fd)
    draw.text((100, band_y + 76), "и раздай троим друзьям", fill=PALE, font=fs)

    # Центр
    draw.text((W / 2 - 200, band_y + 22), "ВРЕМЯ", fill=DIM, font=fs)
    draw.text((W / 2 - 200, band_y + 44), "СВОБОДНОЕ", fill=GOLD, font=fd)
    draw.text((W / 2 - 200, band_y + 76), "хоть 40 минут,   хоть вся следующая неделя",
              fill=PALE, font=fs)

    # Правая панель
    draw.text((W - 380, band_y + 22), "ЦЕНА", fill=DIM, font=fs)
    draw.text((W - 380, band_y + 44), "ТОЛЬКО", fill=GOLD, font=fd)
    draw.text((W - 380, band_y + 76), "интерес · внимание · желание дойти до конца",
              fill=PALE, font=fs)

    # финальная рамка
    draw.rectangle((2, 2, W - 3, H - 3), outline=EDGE, width=2)
    # поверх — лёгкий blur по краям для «потертости»
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    draw = ImageDraw.Draw(img)
    # снова нарисовать рамку, blur её не съел полностью
    draw.rectangle((2, 2, W - 3, H - 3), outline=EDGE, width=2)

    img.save(out_path)
    print(f"  → {out_path}  ({W}×{H}, {out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    random.seed(7)             # детерминированный шум
    render(OUT_DIR / "teaser.png")
