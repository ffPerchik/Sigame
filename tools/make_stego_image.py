#!/usr/bin/env python3
"""
Стеганография: прячет текстовое сообщение в младшие биты (LSB) обычной фотографии.
Носитель — content/Images/stego_carrier.jpg, результат — content/Images/final_photo.png
(PNG, lossless — поэтому LSB не портится). Эта картинка идёт в финальный раунд:
снаружи обычный пейзаж, внутри — послание-загадка.

    python3 tools/make_stego_image.py            # зашить сообщение
    python3 tools/make_stego_image.py --decode    # прочитать обратно (проверка)
"""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CARRIER = ROOT / "content" / "stego_carrier.jpg"
OUT = ROOT / "content" / "Images" / "final_photo.png"

MESSAGE = (
    "ПОСЛЕДНИЙ КАДР — НЕ ПРОСТО КАРТИНКА. ФАЙЛ ПАКЕТА zengame.siq НА САМОМ ДЕЛЕ "
    "ZIP-АРХИВ. ПЕРЕИМЕНУЙ ЕГО В zengame.zip, РАСПАКУЙ И ОТКРОЙ START.txt — "
    "ТАМ НАЧИНАЕТСЯ КВЕСТ. КАЖДЫЙ ИДЁТ САМ."
)


def _bits(buf: bytes):
    for byte in buf:
        for i in range(7, -1, -1):
            yield (byte >> i) & 1


def embed(carrier: Path, message: str, out: Path) -> None:
    img = Image.open(carrier).convert("RGB")
    data = bytearray(img.tobytes())  # сырые байты RGB подряд
    payload = len(message.encode("utf-8")).to_bytes(4, "big") + message.encode("utf-8")
    need = len(payload) * 8
    if need > len(data):
        raise ValueError("Картинка слишком мала для сообщения")
    gen = _bits(payload)
    for i, bit in enumerate(gen):
        data[i] = (data[i] & 0xFE) | bit
    Image.frombytes("RGB", img.size, bytes(data)).save(out, "PNG", optimize=True)
    print(f"зашито {len(payload)} байт в {out.name} ({img.size[0]}x{img.size[1]})")


def decode(path: Path) -> str:
    img = Image.open(path).convert("RGB")
    data = img.tobytes()
    length = 0
    for i in range(32):
        length = (length << 1) | (data[i] & 1)
    out = bytearray()
    bitpos = 32
    for _ in range(length):
        byte = 0
        for _ in range(8):
            byte = (byte << 1) | (data[bitpos] & 1)
            bitpos += 1
        out.append(byte)
    return out.decode("utf-8")


if __name__ == "__main__":
    if "--decode" in sys.argv:
        print(decode(OUT))
    else:
        embed(CARRIER, MESSAGE, OUT)
        print("проверка decode:", decode(OUT)[:60], "...")
