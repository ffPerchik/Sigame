"""Крипто-примитивы квеста (русский алфавит без Ё, 32 буквы)."""
from __future__ import annotations

RU = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
RU_WITH_YO = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
assert len(RU) == 32
assert len(RU_WITH_YO) == 33


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


def vigenere(text: str, key: str, decrypt: bool = False, alphabet: str = RU) -> str:
    """Виженер с выбираемым алфавитом; по умолчанию прежние 32 буквы без Ё."""
    def normalize(ch: str) -> str:
        up = ch.upper()
        return "Е" if up == "Ё" and "Ё" not in alphabet else up

    normalized_key = "".join(normalize(ch) for ch in key if normalize(ch) in alphabet)
    ki = 0
    out = []
    for ch in text:
        up = normalize(ch)
        if up not in alphabet:
            out.append(ch)
            continue
        shift = alphabet.index(normalized_key[ki % len(normalized_key)])
        if decrypt:
            shift = -shift
        out.append(alphabet[(alphabet.index(up) + shift) % len(alphabet)])
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


# Русский брайль (шеститочечные клетки, UNESCO-таблица для кириллицы).
BRAILLE_RU = {
    "а": "1", "б": "12", "в": "2456", "г": "1245", "д": "145", "е": "15",
    "ё": "16", "ж": "245", "з": "1356", "и": "24", "й": "12346", "к": "13",
    "л": "123", "м": "134", "н": "1345", "о": "135", "п": "1234", "р": "1235",
    "с": "234", "т": "2345", "у": "136", "ф": "124", "х": "125", "ц": "14",
    "ч": "12345", "ш": "156", "щ": "1346", "ъ": "12356", "ы": "2346",
    "ь": "23456", "э": "246", "ю": "1256", "я": "1246",
}


def braille_encode(text: str) -> list[str]:
    out = []
    for ch in text.lower():
        if ch == "ё":
            ch = "е"
        if ch in BRAILLE_RU:
            out.append(BRAILLE_RU[ch])
    return out


def braille_decode(cells: list[str]) -> str:
    reverse = {dots: ch for ch, dots in BRAILLE_RU.items()}
    return "".join(reverse.get(cell, "?") for cell in cells)


# Набор символов, который печатает физическая клавиша QWERTY, если
# система ждёт ЙЦУКЕН («смотрел на алфавит с другой стороны»).
QWERTY_TO_YCUKEN = {
    "q": "й", "w": "ц", "e": "у", "r": "к", "t": "е", "y": "н", "u": "г",
    "i": "ш", "o": "щ", "p": "з", "[": "х", "]": "ъ",
    "a": "ф", "s": "ы", "d": "в", "f": "а", "g": "п", "h": "р", "j": "о",
    "k": "к", "l": "л", ";": "д", "'": "э",
    "z": "я", "x": "ч", "c": "с", "v": "м", "b": "и", "n": "т", "m": "ь",
    ",": "б", ".": "ю",
}


def wrong_layout_to_ru(text: str) -> str:
    return "".join(QWERTY_TO_YCUKEN.get(ch.lower(), ch) for ch in text)


# Масонский / pigpen: две решётки 3×3 (прямая и ромбическая),
# каждая без точки и с точкой; из 36 позиций используются первые 32.
PIGPEN_ORDER = RU  # индекс → глиф


def pigpen_cell(idx: int) -> tuple[str, bool, int]:
    """Тип решётки, наличие точки и позиция клетки 0…8."""
    group, pos = divmod(idx, 9)
    dotted = group % 2 == 1
    kind = "box" if group in (0, 1) else "x"
    return kind, dotted, pos
