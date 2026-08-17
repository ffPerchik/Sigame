#!/usr/bin/env python3
"""Генератор «красивого графа разгадки» для ARG «Аргус-1001».

Использует только PIL + numpy (не зависит от matplotlib/networkx).
Стиль Cicada — тёмный фон, неоновое золото, зелёный акцент.

Запуск:
    python3 tools/make_quest_graph.py
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "doc"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---- палитра --------------------------------------------------------------
BG          = (10, 14, 26)
PANEL       = (20, 28, 48)
EDGE        = (54, 66, 96)
CORE        = (24, 36, 64)
GOLD        = (255, 196, 64)
GOLD_SOFT   = (180, 132, 28)
GREEN       = (130, 220, 96)
RED         = (220, 70, 80)
PALE        = (220, 224, 240)
DIM         = (140, 150, 180)

NODE_NUMBERS = {
    "N1": "01", "N2": "02", "N3": "03",
    "N4": "04", "N5": "05", "N6": "06",
}

# ВАЖНО: эмодзи в DejaVu Sans НЕ отрисовываются — используем ASCII-метки.
NODES = [
    {
        "id": "N1", "label": "СНИМОК С КООРДИНАТОЙ",  "tag": "EXIF",
        "tactic": "Публичный EXIF",
        "answer": "Воробьёвы горы",
        "answer2": "55.7105, 37.5404",
        "qr": "ARGUS-WATCH",
        "fragment": "ОТКРОЙ",
        "color": (90, 160, 230),
    },
    {
        "id": "N2", "label": "ГОЛОС В СПЕКТРЕ",       "tag": "FFT",
        "tactic": "Аудио-steganography",
        "answer": "АРГУС + СЛЕД",
        "qr": "—",
        "fragment": "УСЛЫШЬ",
        "color": (220, 110, 200),
    },
    {
        "id": "N3", "label": "ДНЕВНИК С ШИФРОМ",       "tag": "SUB",
        "tactic": "Подстановка + Цезарь +7",
        "answer": "ИЩИ / СВЕТ",
        "qr": "—",
        "fragment": "ПРОЧИТАЙ",
        "color": (240, 200, 110),
    },
    {
        "id": "N4", "label": "КАРТА ПОД НОГАМИ",       "tag": "MP4",
        "tactic": "Скрытое слово в кадре",
        "answer": "СВЕТ",
        "qr": "—",
        "fragment": "НАБЛЮДАЙ",
        "color": (130, 220, 96),
    },
    {
        "id": "N5", "label": "ЦИФРОВАЯ ТЕНЬ",          "tag": "MOD",
        "tactic": "mod 60 → координаты",
        "answer": "55.7333, 37.5833 → Лужники",
        "qr": "ARGUS-LUZHNIKI",
        "fragment": "ВЫЧИСЛИ",
        "color": (220, 140, 90),
    },
    {
        "id": "N6", "label": "КЛЮЧ ЗА ШИФРОМ",         "tag": "A1Z",
        "tactic": "A1Z26 → Цезарь -5",
        "answer": "23-08-11-24 → ЦЗКЧ → СВЕТ",
        "qr": "—",
        "fragment": "ЗАВЕРШИ",
        "color": (190, 130, 230),
    },
]

FRAGMENTS = [n["fragment"] for n in NODES]
FINAL_PHRASE = " · ".join(FRAGMENTS)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def f(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    p = FONT_BOLD if bold else FONT_REG
    if Path(p).exists():
        return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def rounded_box(draw, xy, radius, fill, outline, width=2):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_central_emblem(draw, cx, cy):
    r_outer = 130
    for r, col in ((r_outer, GOLD), (r_outer - 14, GOLD_SOFT), (r_outer - 28, GOLD)):
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=2)
    inner_r = 70
    draw.ellipse((cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r),
                 fill=CORE, outline=GOLD, width=3)
    for i in range(12):
        a = -math.pi / 2 + i * (2 * math.pi / 12)
        rr = r_outer - 6
        x = cx + rr * math.cos(a)
        y = cy + rr * math.sin(a)
        s = 6 if i % 3 == 0 else 3
        draw.ellipse((x - s, y - s, x + s, y + s),
                     fill=GOLD if i % 3 == 0 else GREEN)
    big  = f(38, bold=True)
    small = f(20, bold=False)
    t1 = "ARGVS"
    t2 = "1 0 0 1"
    w1, h1 = text_size(draw, t1, big)
    w2, h2 = text_size(draw, t2, small)
    draw.text((cx - w1 / 2, cy - h1 / 2 - 4), t1, fill=GOLD, font=big)
    draw.text((cx - w2 / 2, cy + h1 / 2 - h2 / 2 + 6), t2, fill=GREEN, font=small)


def draw_node(draw, cx, cy, node):
    """Карточка узла квеста без emoji — ASCII-метка справа."""
    box_w, box_h = 460, 200
    x0, y0 = cx - box_w / 2, cy - box_h / 2
    x1, y1 = cx + box_w / 2, cy + box_h / 2
    color = node["color"]

    # тень
    shadow = (x0 + 6, y0 + 8, x1 + 6, y1 + 8)
    rounded_box(draw, shadow, 14, fill=(0, 0, 0), outline=None)
    # карточка
    rounded_box(draw, (x0, y0, x1, y1), 14, fill=PANEL, outline=color, width=3)

    # номер
    num_x0, num_y0 = x0 + 16, y0 + 16
    num_x1, num_y1 = num_x0 + 62, num_y0 + 62
    rounded_box(draw, (num_x0, num_y0, num_x1, num_y1), 10, fill=color, outline=None)
    fb = f(28, bold=True)
    draw.text((num_x0 + 6, num_y0 + 10), NODE_NUMBERS[node["id"]], fill=(20, 20, 24), font=fb)

    # метка-тег в пилюле слева-внизу
    tag_x0, tag_y0 = num_x0, num_y1 + 8
    tag_x1, tag_y1 = num_x1, tag_y0 + 30
    rounded_box(draw, (tag_x0, tag_y0, tag_x1, tag_y1), 6, fill=color, outline=None)
    ft = f(16, bold=True)
    tw, th = text_size(draw, node["tag"], ft)
    draw.text((tag_x0 + (62 - tw) / 2, tag_y0 + (30 - th) / 2 - 2),
              node["tag"], fill=(20, 20, 24), font=ft)

    # имя узла
    fn = f(20, bold=True)
    draw.text((num_x1 + 14, num_y0 + 18), node["label"], fill=PALE, font=fn)

    # тактика (метод)
    fmeta = f(15)
    fmeta_b = f(15, bold=True)
    draw.text((x0 + 18, y0 + 92), "метод:", fill=DIM, font=fmeta)
    aw1 = text_size(draw, "метод: ", fmeta)[0]
    draw.text((x0 + 18 + aw1, y0 + 92), node["tactic"], fill=color, font=fmeta_b)

    # ответ (зелёный)
    fans = f(26, bold=True)
    aw2 = text_size(draw, "ответ:   ", fmeta)[0]
    draw.text((x0 + 18, y0 + 126), "ответ:", fill=DIM, font=fmeta)
    draw.text((x0 + 18 + aw2, y0 + 122), node["answer"], fill=GREEN, font=fans)

    # фрагмент
    ffrag = f(15)
    ffrag_b = f(18, bold=True)
    draw.text((x0 + 18, y1 - 26), "фрагмент:", fill=DIM, font=ffrag)
    fw = text_size(draw, "фрагмент: ", ffrag)[0]
    draw.text((x0 + 18 + fw, y1 - 30), node["fragment"], fill=GOLD, font=ffrag_b)

    # мини-эмблема справа вверху (ромбик-печать)
    em_x = x1 - 26
    em_y = y0 + 28
    sz = 14
    pts = [(em_x, em_y - sz), (em_x + sz, em_y), (em_x, em_y + sz), (em_x - sz, em_y)]
    draw.polygon(pts, outline=color, width=2)
    inner = [(em_x, em_y - sz + 5), (em_x + sz - 5, em_y),
             (em_x, em_y + sz - 5), (em_x - sz + 5, em_y)]
    draw.polygon(inner, fill=color)


def draw_connector(draw, fxy, txy, color, width=2, dashed=False):
    if dashed:
        x0, y0 = fxy
        x1, y1 = txy
        dx, dy = x1 - x0, y1 - y0
        dist = math.hypot(dx, dy)
        steps = int(dist // 12)
        for i in range(0, steps, 2):
            t0 = i / steps
            t1 = (i + 1) / steps
            sx, sy = x0 + dx * t0, y0 + dy * t0
            ex, ey = x0 + dx * t1, y0 + dy * t1
            draw.line([(sx, sy), (ex, ey)], fill=color, width=width)
    else:
        draw.line([fxy, txy], fill=color, width=width)


def draw_header(draw, W):
    fb = f(44, bold=True)
    title = "ARGVS · 1001 · СЕАНС"
    w, _ = text_size(draw, title, fb)
    draw.text(((W - w) / 2, 30), title, fill=GOLD, font=fb)
    sub = f(18)
    st = "полная разгадка ARG-квеста  ·  шесть узлов  ·  шесть фрагментов"
    w, _ = text_size(draw, st, sub)
    draw.text(((W - w) / 2, 88), st, fill=DIM, font=sub)
    draw.line([(220, 124), (W - 220, 124)], fill=EDGE, width=1)


def draw_final_banner(draw, W, H):
    h_banner = 100
    y0 = H - h_banner - 18
    y1 = H - 18
    draw.rounded_rectangle((40, y0, W - 40, y1), 18,
                           fill=(20, 32, 22), outline=GREEN, width=3)
    ft = f(22, bold=False)
    fs = f(34, bold=True)
    label = "ПОСЛАНИЕ  →"
    lw, _ = text_size(draw, label, ft)
    draw.text((80, y0 + 16), label, fill=DIM, font=ft)
    x = 80 + lw + 24
    for i, frag in enumerate(FRAGMENTS):
        col = NODES[i]["color"]
        text_w, _ = text_size(draw, frag, fs)
        draw.text((x, y0 + 22), frag, fill=col, font=fs)
        x += text_w + 22
        if i < len(FRAGMENTS) - 1:
            d = "·"
            dw, _ = text_size(draw, d, fs)
            draw.text((x, y0 + 22), d, fill=DIM, font=fs)
            x += dw + 18


def draw_legend(draw, W, H):
    f1 = f(13)
    f2 = f(13, bold=True)
    y = 154
    draw.text((40, y), "ИНСТРУМЕНТЫ", fill=GOLD, font=f2)
    yy = y + 22
    items = [
        ("EXIF/GPS", "exiftool / properties"),
        ("Spectrogram", "Audacity / Spek / Sonic Visualiser"),
        ("CAESAR", "32 буквы, без ё"),
        ("A1Z26", "А=1, Б=2, …, Я=32"),
        ("Substitution", "по ключу на картинке"),
    ]
    for k, v in items:
        draw.text((40, yy), k + ":", fill=DIM, font=f2)
        kw, _ = text_size(draw, k + ": ", f2)
        draw.text((40 + kw, yy), v, fill=PALE, font=f1)
        yy += 20


def draw_qr_branches(draw, W, H):
    """QR-коды — в правой верхней зоне, где много пустого места."""
    padding = 24
    box_w = 320
    box_h = 110
    x = W - box_w - padding
    y = 158
    draw.rounded_rectangle((x, y, x + box_w, y + box_h), 12,
                           fill=PANEL, outline=GOLD, width=2)
    fbig = f(17, bold=True)
    draw.text((x + 16, y + 12), "QR НА ЛОКАЦИЯХ", fill=GOLD, font=fbig)
    yy = y + 40
    entries = [
        ("ARGUS-WATCH",     "Воробьёвы горы · смотровая"),
        ("ARGUS-LUZHNIKI",  "Лужники · опора освещения"),
    ]
    for code, place in entries:
        fb = f(14, bold=True)
        draw.text((x + 16, yy), "QR:", fill=DIM, font=fb)
        bw, _ = text_size(draw, "QR: ", fb)
        draw.text((x + 16 + bw, yy - 1), code, fill=RED, font=fb)
        sub = f(13)
        draw.text((x + 16, yy + 20), place, fill=PALE, font=sub)
        yy += 38


def render(out_path: Path):
    W, H = 1900, 1420
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw_header(draw, W)
    draw_legend(draw, W, H)

    cx, cy = W / 2, H / 2 - 30
    draw_central_emblem(draw, int(cx), int(cy))

    RY, RX = 410, 720
    positions = []
    for i in range(6):
        a = -math.pi / 2 + i * (2 * math.pi / 6)
        positions.append((cx + RX * math.cos(a), cy + RY * math.sin(a)))

    # центр → узлы
    for px, py in positions:
        # линия обрезается до края карточки
        dx_, dy_ = px - cx, py - cy
        L = math.hypot(dx_, dy_)
        ux, uy = dx_ / L, dy_ / L
        # старт от края кольца
        sx = cx + ux * (130 - 2)
        sy = cy + uy * (130 - 2)
        # конец у края карточки (примерно)
        ex = px - ux * 240
        ey = py - uy * 110
        draw.line([(sx, sy), (ex, ey)], fill=GREEN, width=2)

    # пунктир узел↔узел
    for i in range(6):
        for j in (i + 1, i + 2):
            jj = j % 6
            draw_connector(draw, positions[i], positions[jj],
                           color=EDGE, width=1, dashed=True)

    for node, (px, py) in zip(NODES, positions):
        draw_node(draw, int(px), int(py), node)

    draw_final_banner(draw, W, H)
    draw_qr_branches(draw, W, H)

    draw.rectangle((2, 2, W - 3, H - 3), outline=EDGE, width=2)
    img.save(out_path)
    print(f"  → {out_path}  ({W}×{H}, {out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    render(OUT_DIR / "walkthrough_graph.png")
