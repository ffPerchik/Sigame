#!/usr/bin/env python3
"""Генерирует QR-коды для qr-стадий квеста (deep link на бота).

Каждый QR кодирует https://t.me/<BOT_USERNAME>?start=<CODE> — игрок сканирует,
открывается бот, шаг засчитывается автоматически.
Картинки кладутся в bot/qr/<stage_id>.png.

    python3 bot/make_qr.py
"""
import os
import sys
from pathlib import Path

import qrcode

# конфиг без жёсткой проверки токена
os.environ.setdefault("BOT_TOKEN", "0:skip")
os.environ.setdefault("HOST_ID", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg  # noqa: E402
import quest  # noqa: E402

OUT = Path(__file__).resolve().parent / "qr"
OUT.mkdir(exist_ok=True)

if not cfg.BOT_USERNAME:
    print("ВНИМАНИЕ: BOT_USERNAME не задан в .env — QR будут без ссылки на бота.")
    base = "https://t.me/?start="  # заглушка
else:
    base = f"https://t.me/{cfg.BOT_USERNAME}?start="

n = 0
for stage_id, code in quest.qr_stages().items():
    url = base + str(code)
    img = qrcode.make(url)
    img.save(OUT / f"{stage_id}.png")
    print(f"  {stage_id}.png  ←  {url}")
    n += 1

print(f"\nГотово: {n} QR в {OUT}. Распечатай и спрячь на локациях.")
