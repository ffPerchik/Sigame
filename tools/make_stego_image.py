#!/usr/bin/env python3
"""
Стеганография для НЕ-программистов: сообщение находят обычные онлайн-сервисы.

Два независимых способа обнаружения:
  1. LSB в пикселях — стандартная схема (RGB, MSB-first, без длины, с null-терминатором),
     сообщение — чистый ASCII. Так её читают популярные LSB-декодеры и zsteg.
  2. PNG tEXt-метаданные (ключ "Comment") — видит любой EXIF/metadata-вьюер.

Носитель — content/stego_carrier.jpg, результат — content/Images/final_photo.png.

    python3 tools/make_stego_image.py            # спрятать
    python3 tools/make_stego_image.py --decode    # прочитать (LSB)
"""
import sys
from pathlib import Path
from PIL import Image
from PIL.PngImagePlugin import PngInfo

ROOT = Path(__file__).resolve().parent.parent
CARRIER = ROOT / "content" / "stego_carrier.jpg"
OUT = ROOT / "content" / "Images" / "final_photo.png"

# Чистый ASCII — чтобы любой LSB-декодер показывал читаемый текст.
MESSAGE = (
    "HIDDEN MESSAGE.\n"
    "zengame.siq is actually a ZIP archive.\n"
    "Rename it to zengame.zip, extract, and open START.txt -- the quest begins.\n"
    "Each player goes alone. Good luck."
)


def _bits(buf: bytes):
    for byte in buf:
        for i in range(7, -1, -1):       # MSB-first — стандарт для LSB-декодеров
            yield (byte >> i) & 1


def embed(carrier: Path, message: str, out: Path) -> None:
    img = Image.open(carrier).convert("RGB")
    data = bytearray(img.tobytes())
    payload = message.encode("ascii") + b"\x00"   # null-терминатор вместо length-префикса
    bits = list(_bits(payload))
    if len(bits) > len(data):
        raise ValueError("Картинка мала для сообщения")
    for i, bit in enumerate(bits):
        data[i] = (data[i] & 0xFE) | bit
    Image.frombytes("RGB", img.size, bytes(data)).save(out, "PNG", optimize=True,
                                                         pnginfo=_meta(message))
    print(f"LSB: зашито {len(payload)} ASCII-байт (MSB-first, RGB) + null. "
          f"Метаданные Comment добавлены.")


def _meta(message: str) -> PngInfo:
    meta = PngInfo()
    meta.add_text("Comment", message)     # видит любой metadata/EXIF-вьюер
    meta.add_text("Description", "zengame stego")
    return meta


def decode(path: Path) -> str:
    img = Image.open(path).convert("RGB")
    data = img.tobytes()
    out = bytearray()
    bitpos = 0
    while bitpos + 8 <= len(data):
        byte = 0
        for _ in range(8):                 # MSB-first
            byte = (byte << 1) | (data[bitpos] & 1)
            bitpos += 1
        if byte == 0:                      # null-терминатор
            break
        out.append(byte)
    return out.decode("ascii", errors="replace")


def decode_lsb_first(path: Path) -> str:
    """Как бы прочёл декодер с обратным порядком бит (для диагностики)."""
    img = Image.open(path).convert("RGB")
    data = img.tobytes()
    out = bytearray()
    bitpos = 0
    while bitpos + 8 <= len(data):
        byte = 0
        for k in range(8):                 # LSB-first
            byte |= (data[bitpos] & 1) << k
            bitpos += 1
        if byte == 0:
            break
        out.append(byte)
    return out.decode("ascii", errors="replace")


if __name__ == "__main__":
    if "--decode" in sys.argv:
        print("=== LSB (MSB-first, стандарт) ===")
        print(decode(OUT))
    else:
        embed(CARRIER, MESSAGE, OUT)
        print("\nПроверка извлечения (MSB-first):")
        print(decode(OUT))
        print("\n(диагностика) LSB-first даёт:", repr(decode_lsb_first(OUT)[:40]))
