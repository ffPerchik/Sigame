#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборщик пакета «Турнир Трёх» (.siq) + встроенный ARG-квест.

Что делает скрипт:
  1. Читает master-файл content.xml (источник вопросов).
  2. ПРОВЕРЯЕТ мета-шифр раунда 1: из ответов извлекаются 20 букв
     (позиция = цена/100, чтение по строкам цен) -> фраза-пароль.
  3. Подбирает медиа (картинки/голос) из папок Image/ и media/.
  4. Генерирует QR-код первой точки квеста (media/quest/qr_точка_1.png).
  5. Собирает _hidden/start.zip (пароль = транслит фразы) и кладёт его ВНУТРЬ пакета.
  6. Прячет стего-сообщение в конце картинки r1_grumpy_cat.jpg (этап 5 квеста).
  7. Собирает итоговый файл Turnir_Treh.siq.

Запуск:  python3 generate_siq.py [--qr "текст для QR-кода"]
"""

import io
import os
import re
import sys
import uuid
import zipfile
from xml.etree import ElementTree as ET

ROOT = os.path.dirname(os.path.abspath(__file__))
CONTENT_XML = os.path.join(ROOT, "content.xml")
OUTPUT_SIQ = os.path.join(ROOT, "Turnir_Treh.siq")

MEDIA_DIRS = [os.path.join(ROOT, "Image"), os.path.join(ROOT, "media", "images"), os.path.join(ROOT, "media", "audio")]
QUEST_DIR = os.path.join(ROOT, "media", "quest")

EXPECTED_PHRASE = "СЛЕДУЙЗАГОЛОСОМВЕТРА"

# Транслит для пароля start.zip (стандартные правила)
TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

STEGO_IMAGE = "r1_grumpy_cat.jpg"
STEGO_MARKER = "CICADA_3301_STAGE_5"
STEGO_MESSAGE = """-----BEGIN {marker}-----
ТЫ ДОШЁЛ ДО КОНЦА. ЭТОТ КОТ ЗНАЛ ВСЁ С САМОГО НАЧАЛА.

ВЕРНИСЬ К ИГРЕ (файл .siq).
1. ОТКРОЙ РАУНД 3 «НАША КОМПАНИЯ», ТЕМУ «НАШИ МЕСТА», ВОПРОС ЗА 500.
   ВОЗЬМИ ВТОРУЮ БУКВУ ЕГО ОТВЕТА.
2. ОТКРОЙ ТЕМУ «ИСТОРИЯ ТРОИЦЫ», ВОПРОС ЗА 100.
   ВОЗЬМИ ПОСЛЕДНЮЮ БУКВУ ЕГО ОТВЕТА.
3. СЛОЖИ ЭТИ ДВЕ БУКВЫ — ПОЛУЧИТСЯ ФИНАЛЬНЫЙ КОД.
4. НАЗОВИ КОД ВЕДУЩЕМУ. ТЫ ПОБЕДИЛ.

Если не помнишь ответы — открой content.xml и прочитай их.
-----END {marker}-----
""".format(marker=STEGO_MARKER)


def normalize(text: str) -> str:
    """Ответ без пробелов, дефисов и знаков препинания (для счёта букв)."""
    return re.sub(r"[\s\-—–«»\"'.,!?()\[\]]", "", text)


def letters_only(text: str) -> str:
    return re.sub(r"[^А-Яа-яЁёA-Za-z]", "", text)


def translit(text: str) -> str:
    return "".join(TRANSLIT.get(ch.lower(), ch.lower()) for ch in text)


def local(tag: str):
    """Имя тега без namespace (у пакета есть xmlns)."""
    return tag.split("}", 1)[-1]


def find_all(el, path):
    return [c for c in el.iter() if c is not el and local(c.tag) == path.split("/")[-1]]


def find_first(el, tag):
    for c in el.iter():
        if local(c.tag) == tag:
            return c
    return None


def parse_package(xml_path: str):
    """Возвращает структуру: list of (round_name, round_type, [(theme, [(price, scenario_text, answers, comment)])])"""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    rounds = []
    for rnd in find_all(root, "round"):
        rname = rnd.get("name", "")
        rtype = rnd.get("type", "standart")
        themes = []
        for theme in find_all(rnd, "theme"):
            questions = []
            for q in find_all(theme, "question"):
                price = int(q.get("price", 0))
                scenario = " ".join(a.text or "" for a in find_all(q, "atom"))
                answers = [a.text or "" for a in find_all(q, "answer")]
                comment_el = find_first(q, "comments")
                comment = comment_el.text if comment_el is not None and comment_el.text else ""
                questions.append((price, scenario, answers, comment))
            themes.append((theme.get("name", ""), questions))
        rounds.append((rname, rtype, themes))
    return root, rounds


def verify_cipher(rounds):
    """Проверка мета-шифра раунда 1. Возвращает (phrase, table)."""
    rnd = next((r for r in rounds if r[0].startswith("Раунд 1")), None)
    if rnd is None:
        print("!! Раунд 1 не найден")
        return None, []
    # темы раунда 1 в порядке следования
    themes = rnd[2]
    # собираем ответы по ценам: price -> [(theme_idx, answer)]
    by_price = {}
    for ti, (tname, questions) in enumerate(themes):
        for price, _, answers, _ in questions:
            by_price.setdefault(price, []).append((ti, answers[0] if answers else ""))
    phrase = ""
    table = []
    for price in sorted(by_price):
        pos = price // 100
        for ti, answer in by_price[price]:
            norm = normalize(answer)
            if pos < 1 or pos > len(norm):
                letter = "?"
            else:
                letter = norm[pos - 1]
            phrase += letter
            table.append((price, themes[ti][0], answer, pos, letter))
    return phrase, table


def find_media(filename: str):
    """Ищет файл по имени в MEDIA_DIRS."""
    for d in MEDIA_DIRS:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    return None


def collect_media(root):
    """Собирает все @файлы, упомянутые в атомах."""
    needed = set()
    for atom in find_all(root, "atom"):
        if atom.text and atom.text.startswith("@"):
            needed.add(atom.text[1:])
    media = {}
    missing = []
    for fname in sorted(needed):
        path = find_media(fname)
        if path:
            media[fname] = path
        else:
            missing.append(fname)
    return media, missing


def make_qr(payload: str, out_path: str):
    import qrcode
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(out_path)
    print("QR сохранён:", out_path)


def make_start_zip(password: str):
    """Создаёт _hidden/start.zip (в памяти) с файлами квеста.

    Пароль: AES-256 (открывается 7-Zip / WinRAR; штатный zip Windows не умеет AES).
    """
    try:
        import pyzipper
    except ImportError:
        print("!! Установите зависимость: pip install pyzipper")
        raise
    buf = io.BytesIO()
    with pyzipper.AESZipFile(buf, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as z:
        z.setpassword(password.encode("utf-8"))
        for fname in ["ЧТО_ЭТО.txt", "записка_точка_1.txt"]:
            p = os.path.join(QUEST_DIR, fname)
            if os.path.exists(p):
                z.write(p, fname)
        voice = os.path.join(QUEST_DIR, "голос_ветра.mp3")
        if not os.path.exists(voice):
            voice = os.path.join(QUEST_DIR, "golos_vetra.mp3")
        if os.path.exists(voice):
            z.write(voice, "голос_ветра.mp3")
        qr = os.path.join(QUEST_DIR, "qr_точка_1.png")
        if os.path.exists(qr):
            z.write(qr, "qr_точка_1.png")
    buf.seek(0)
    return buf.getvalue()


def add_stego(image_bytes: bytes) -> bytes:
    """Дописывает стего-сообщение в конец JPEG (после маркера FFD9)."""
    if STEGO_MARKER.encode() in image_bytes:
        return image_bytes  # уже добавлено
    idx = image_bytes.rfind(b"\xff\xd9")
    if idx == -1:
        idx = len(image_bytes)
    else:
        idx += 2
    block = ("\n" + STEGO_MESSAGE + "\n").encode("utf-8")
    return image_bytes[:idx] + block + image_bytes[idx:]


def build(qr_payload: str = None):
    root, rounds = parse_package(CONTENT_XML)

    # 1. Шифр
    phrase, table = verify_cipher(rounds)
    print("=== МЕТА-ШИФР РАУНДА 1 ===")
    for price, theme, answer, pos, letter in table:
        print(f"  {price:>4} | {theme:<28} | {answer:<20} | буква №{pos} = {letter}")
    phrase = (phrase or "").upper()
    print("Фраза:", phrase)
    if phrase != EXPECTED_PHRASE:
        print("!! ВНИМАНИЕ: фраза отличается от ожидаемой!", EXPECTED_PHRASE)
        print("   Если вы меняли ответы раунда 1, пароль изменится автоматически.")
    password = translit(phrase)
    print("Пароль start.zip (латиница):", password)

    # 2. Незаполненные ответы раунда 3
    unfilled = []
    for rname, rtype, themes in rounds:
        if "Наша компания" in rname:
            for tname, questions in themes:
                for price, _, answers, _ in questions:
                    if answers and answers[0].startswith("[ЗАПОЛНИ"):
                        unfilled.append((tname, price))
    if unfilled:
        print("!! НЕ ЗАПОЛНЕНЫ ОТВЕТЫ РАУНДА 3 (ведущий должен заменить перед игрой):")
        for t, p in unfilled:
            print(f"   - {t}, {p}")

    # 3. Медиа
    media, missing = collect_media(root)
    if missing:
        print("!! Не найдены медиафайлы:", missing)
    for f in media:
        print("Медиа:", f, "->", os.path.relpath(media[f], ROOT))

    # 4. QR
    qr_path = os.path.join(QUEST_DIR, "qr_точка_1.png")
    if qr_payload is None:
        qr_payload = os.environ.get("QR_PAYLOAD", "ТОЧКА 1: набережная, скамейка у старого моста. Под ней конверт №1.")
    make_qr(qr_payload, qr_path)

    # 5. start.zip
    start_zip = make_start_zip(password)
    print("start.zip собран:", len(start_zip), "байт, пароль:", password)

    # 6. Собираем .siq
    content_types = """<?xml version="1.0" encoding="utf-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="si/xml" /><Default Extension="mp3" ContentType="si/audio" /><Default Extension="jpg" ContentType="si/image" /><Default Extension="png" ContentType="si/image" /><Default Extension="mp4" ContentType="si/video" /></Types>"""
    authors_xml = '<?xml version="1.0" encoding="utf-8"?><Authors />'
    sources_xml = '<?xml version="1.0" encoding="utf-8"?><Sources />'

    if os.path.exists(OUTPUT_SIQ):
        os.remove(OUTPUT_SIQ)
    with zipfile.ZipFile(OUTPUT_SIQ, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("content.xml", open(CONTENT_XML, encoding="utf-8").read())
        z.writestr("Texts/authors.xml", authors_xml)
        z.writestr("Texts/sources.xml", sources_xml)
        for fname, path in media.items():
            data = open(path, "rb").read()
            if fname == STEGO_IMAGE:
                data = add_stego(data)
                print("Стего-сообщение добавлено в", fname)
            z.writestr("Images/" + fname, data)
        z.writestr("_hidden/start.zip", start_zip)

    size = os.path.getsize(OUTPUT_SIQ)
    print("=== ГОТОВО ===")
    print("Пакет:", OUTPUT_SIQ, f"({size/1024:.0f} КБ)")
    print("Внутри пакета: _hidden/start.zip (пароль:", password + ") и скрытое стего в Images/" + STEGO_IMAGE)
    return OUTPUT_SIQ


if __name__ == "__main__":
    qr = None
    if len(sys.argv) > 1 and sys.argv[1] == "--qr" and len(sys.argv) > 2:
        qr = sys.argv[2]
    build(qr)
