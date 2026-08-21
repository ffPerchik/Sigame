"""Крипто-примитивы квеста (русский алфавит без Ё, 32 буквы)."""
from __future__ import annotations

RU = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
assert len(RU) == 32


def only_ru(s: str) -> str:
    return "".join(ch for ch in s.upper().replace("Ё", "Е") if ch in RU)


def a1z26_encode(text: str) -> str:
    return "-".join(f"{RU.index(ch) + 1:02d}" for ch in only_ru(text))


def a1z26_decode(nums: str) -> str:
    out = []
    for part in nums.replace(",", " ").replace("-", " ").split():
        out.append(RU[int(part) - 1])
    return "".join(out)


def caesar(text: str, shift: int) -> str:
    out = []
    for ch in text:
        up = ch.upper().replace("Ё", "Е")
        if up in RU:
            i = (RU.index(up) + shift) % 32
            out.append(RU[i] if ch.isupper() or ch in RU else RU[i].lower())
        else:
            out.append(ch)
    return "".join(out)


def atbash(text: str) -> str:
    out = []
    for ch in text:
        up = ch.upper().replace("Ё", "Е")
        if up in RU:
            out.append(RU[31 - RU.index(up)])
        else:
            out.append(ch)
    return "".join(out)


def vigenere(text: str, key: str, decrypt: bool = False) -> str:
    key = only_ru(key)
    ki = 0
    out = []
    for ch in text:
        up = ch.upper().replace("Ё", "Е")
        if up not in RU:
            out.append(ch)
            continue
        shift = RU.index(key[ki % len(key)])
        if decrypt:
            shift = -shift
        out.append(RU[(RU.index(up) + shift) % 32])
        ki += 1
    return "".join(out)


def rail_fence_enc(text: str, rails: int = 3) -> str:
    text = only_ru(text)
    fence = [[] for _ in range(rails)]
    rail, d = 0, 1
    for ch in text:
        fence[rail].append(ch)
        rail += d
        if rail == 0 or rail == rails - 1:
            d *= -1
    return "".join("".join(r) for r in fence)


def rail_fence_dec(cipher: str, rails: int = 3) -> str:
    cipher = only_ru(cipher)
    n = len(cipher)
    pattern = []
    rail, d = 0, 1
    for _ in range(n):
        pattern.append(rail)
        rail += d
        if rail == 0 or rail == rails - 1:
            d *= -1
    counts = [pattern.count(r) for r in range(rails)]
    chunks, i = [], 0
    for c in counts:
        chunks.append(list(cipher[i:i + c]))
        i += c
    out = []
    for r in pattern:
        out.append(chunks[r].pop(0))
    return "".join(out)


# Масонский / pigpen: 4 группы по 9, используем 32 символа (последние 4 группы урезаны)
PIGPEN_ORDER = RU  # индекс → глиф


def pigpen_cell(idx: int) -> tuple[str, bool]:
    """Тип глифа и точка."""
    group, pos = divmod(idx, 9)
    dotted = group % 2 == 1
    kind = "box" if group in (0, 1) else "x"
    return kind, dotted, pos
