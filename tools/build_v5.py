#!/usr/bin/env python3
"""
Сборка финального пакета SIGame (формат v5) из заготовки Zengame.siq.

Что делает:
  1. Читает content.xml и всё медиа прямо из Zengame.siq (без распаковки на диск).
  2. Перераспределяет 27 исходных тем по 5 раундам (Раунд 1 — полностью
     тематический «География»), перенося <theme> целиком (спецтипы и медиа-ссылки
     сохраняются).
  3. Добавляет две новые темы в формате v5: «Армянская еда» и «BTS»
     (фото → название; картинки берутся из content/Images/).
  4. Регенерирует <files>-манифест (sha256) для добавленных картинок.
  5. Собирает новый .siq: content.xml + [Content].xml + всё медиа + мои картинки.

Запуск:
    python3 tools/build_v5.py
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "https://github.com/VladimirKhil/SI/blob/master/assets/siq_5.xsd"
ET.register_namespace("", NS)

ROOT = Path(__file__).resolve().parent.parent
ZEN = ROOT / "Zengame.siq"
MY_IMAGES = ROOT / "content" / "Images"
OUT_SIQ = ROOT / "Своя игра для друзей.siq"


def q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


# ---- конструирование v5-вопросов ----

def _item(parent, text=None, type=None, is_ref=False, placement=None):
    it = ET.SubElement(parent, q("item"))
    if type:
        it.set("type", type)
    if is_ref:
        it.set("isRef", "True")
    if placement:
        it.set("placement", placement)
    if text is not None:
        it.text = text
    return it


def make_question(price, question_items, answers):
    qel = ET.Element(q("question"), {"price": str(price)})
    params = ET.SubElement(qel, q("params"))
    pq = ET.SubElement(params, q("param"), {"name": "question", "type": "content"})
    for kind, val in question_items:
        if kind == "text":
            _item(pq, text=val)
        elif kind == "image":
            _item(pq, type="image", is_ref=True, text=val)
        elif kind == "audio":
            _item(pq, type="audio", is_ref=True, placement="background", text=val)
    right = ET.SubElement(qel, q("right"))
    for a in answers:
        ET.SubElement(right, q("answer")).text = a
    return qel


def build_armenian_theme():
    th = ET.Element(q("theme"), {"name": "Армянская еда 🍽"})
    qs = ET.SubElement(th, q("questions"))
    data = [
        (100, [("text", "Назовите этот армянский хлеб — его пекут в тони́ре, а в 2014 году внесли в список нематериального наследия ЮНЕСКО."),
               ("image", "arm-lavash.jpg")], ["Лаваш"]),
        (200, [("text", "В виноградные листья завёрнут фарш с рисом. Что это за блюдо?"),
               ("image", "arm-dolma.jpg")], ["Долма", "Толма"]),
        (300, [("text", "Как армяне называют шашлык — мясо на углях?"),
               ("image", "arm-khorovats.jpg")], ["Хоровац", "Хоровадз"]),
        (400, [("text", "Эти гладкие мясные шары — тщательно отбитая телятина. Назовите блюдо."),
               ("image", "arm-kufta.jpg")], ["Кюфта"]),
        (500, [("text", "Праздничная тыква, фаршированная рисом, сухофруктами и мёдом. Как называется блюдо?"),
               ("image", "arm-ghapama.jpg")], ["Хапама", "Гапама", "Капама"]),
    ]
    for price, items, ans in data:
        qs.append(make_question(price, items, ans))
    return th


def build_bts_theme():
    th = ET.Element(q("theme"), {"name": "BTS 🎤"})
    qs = ET.SubElement(th, q("questions"))
    members = [
        (100, "bts-rm.jpg",       ["RM", "Ким Намджун", "Намджун", "Ким Нам-джун"]),
        (200, "bts-jin.jpg",      ["Jin", "Джин", "Ким Сокджин", "Сокджин"]),
        (300, "bts-suga.jpg",     ["Suga", "Шуга", "Мин Юнги", "Юнги", "Agust D", "Агуст D"]),
        (400, "bts-jhope.jpg",    ["J-Hope", "Джей-Хоуп", "Чон Хосок", "Хосок", "Хоби"]),
        (500, "bts-jimin.jpg",    ["Jimin", "Чимин", "Пак Чимин"]),
        (600, "bts-v.jpg",        ["V", "Ви", "Ким Тэхён", "Тэхён"]),
        (700, "bts-jungkook.jpg", ["Jungkook", "Чонгук", "Чон Чонгук", "Golden Maknae"]),
    ]
    prompt = "Назовите участника группы BTS (сценическое или настоящее имя)."
    for price, img, ans in members:
        qs.append(make_question(price, [("text", prompt), ("image", img)], ans))
    return th


def build_quest_theme():
    """Тема-крючок квеста: 1 вопрос с картинкой-подсказкой.
    Картинка прямо ведёт: переименуй .siq в .zip и распакуй. Внутри пакета
    спрятан START.txt (см. QUEST_START ниже) — реальный старт квеста."""
    th = ET.Element(q("theme"), {"name": "🧩 Послание"})
    qs = ET.SubElement(th, q("questions"))
    items = [
        ("text", "В пакете спрятано послание. Разгадай, что нужно сделать с файлом, чтобы его найти."),
        ("image", "quest_hint.jpg"),
    ]
    answers = [".zip", "zip", "зип", "переименовать в zip", "переименовать в .zip", "архив"]
    qs.append(make_question(500, items, answers))
    return th


INJECTORS = {"armenian": build_armenian_theme, "bts": build_bts_theme, "quest": build_quest_theme}

# ---- план раундов: (название, [индексы исходных тем], [инъекции]) ----
ROUND_PLAN = [
    ("Раунд 1 — География",            [4, 15, 16, 19, 21, 25], []),
    ("Раунд 2 — Кино, мультики, мемы", [0, 1, 3, 5, 13, 8],    []),
    ("Раунд 3 — Музыка и стиль",       [9, 14, 18, 10, 23],    []),
    ("Раунд 4 — Игры и головоломки",   [7, 12, 22, 24, 6, 11], []),
    ("Раунд 5 — Микс + бонус",         [2, 17, 20, 26],         ["armenian", "bts", "quest"]),
]


def quest_start_text() -> str:
    """Скрытый START.txt внутри .siq — первый (расширяемый) шаг квеста."""
    secret = ("ПОЗДРАВЛЯЮ. ТЫ НАШЁЛ ВХОД В ИНДИВИДУАЛЬНЫЙ КВЕСТ — "
              "КАЖДЫЙ ИДЁТ САМ ЗА СЕБЯ. СЛЕДУЮЩИЙ СЛОЙ БУДЕТ СПРЯТАН ГЛУБЖЕ: "
              "В КАРТИНКАХ, В ОТВЕТАХ, В РЕАЛЬНЫХ ТОЧКАХ. "
              "ХОРОШО СПРЯТАННОЕ — ХОРОШО НАЙДЁННОЕ.")
    blob = base64.b64encode(secret.encode("utf-8")).decode("ascii")
    blob_lines = "\n".join(blob[i:i + 64] for i in range(0, len(blob), 64))
    return (
        "   ╔══════════════════════════════════════════════╗\n"
        "   ║   ВЫ НАШЛИ НАЧАЛО                             ║\n"
        "   ╚══════════════════════════════════════════════╝\n"
        "\n"
        "   Тот, кто читает это, — перестал быть просто игроком.\n"
        "   Дальше каждый сам за себя.\n"
        "\n"
        "   Первое послание закодировано (Base64 → UTF-8). Расшифруй:\n"
        "\n"
        f"{blob_lines}\n"
        "\n"
        "   — хороший поиск вознаграждается. Продолжение следует.\n"
    )


def main() -> int:
    if not ZEN.exists():
        print(f"Zengame.siq не найден: {ZEN}", file=sys.stderr)
        return 1

    with zipfile.ZipFile(ZEN) as z:
        content = z.read("content.xml")
        all_names = z.namelist()
        root_files = {"content.xml", "[Content].xml", "quality.marker"}
        media = {}
        for n in all_names:
            if n in root_files or n.endswith("/"):
                continue
            media[n] = z.read(n)
        qm = z.read("quality.marker") if "quality.marker" in all_names else None

    root = ET.fromstring(content)
    orig_round = root.find(f"{q('rounds')}/{q('round')}")
    if orig_round is None:
        print("В content.xml не найден <rounds><round>", file=sys.stderr)
        return 1
    orig_themes_el = orig_round.find(f"{q('themes')}")
    theme_list = orig_themes_el.findall(f"{q('theme')}")
    print(f"исходных тем: {len(theme_list)}")

    # проверка покрытия
    used = set()
    for _, idxs, _ in ROUND_PLAN:
        used.update(idxs)
    missing = set(range(len(theme_list))) - used
    if missing:
        print(f"⚠ темы без раунда (индексы): {sorted(missing)}", file=sys.stderr)

    # detached themes by index
    by_idx = {i: t for i, t in enumerate(theme_list)}

    # пересобираем <rounds>
    rounds_el = root.find(f"{q('rounds')}")
    rounds_el.remove(orig_round)
    for rname, idxs, inject in ROUND_PLAN:
        r = ET.SubElement(rounds_el, q("round"), {"name": rname})
        ths = ET.SubElement(r, q("themes"))
        for i in idxs:
            ths.append(by_idx[i])
        for inj in inject:
            ths.append(INJECTORS[inj]())
        n_themes = len(ths)
        n_qs = sum(len(t.find(f"{q('questions')}").findall(f"{q('question')}"))
                   for t in ths)
        print(f"  {rname}: тем={n_themes}, вопросов={n_qs}")

    # имя/дата пакета
    root.set("name", "Своя игра для друзей")
    root.set("date", datetime.date.today().strftime("%d.%m.%Y"))

    # манифест <files>: добавляем свои картинки
    files_el = root.find(f"{q('files')}")
    existing = {f.attrib["name"] for f in files_el.findall(f"{q('file')}")}
    added = 0
    if MY_IMAGES.is_dir():
        for img in sorted(MY_IMAGES.iterdir()):
            if img.suffix.lower() not in (".jpg", ".jpeg", ".png", ".gif"):
                continue
            fname = f"Images/{img.name}"
            data = img.read_bytes()
            if fname not in existing:
                h = hashlib.sha256(data).hexdigest().upper()
                ET.SubElement(files_el, q("file"), {"name": fname, "hash": h})
                media[fname] = data
                added += 1
    print(f"добавлено картинок в манифест: {added}")

    # сериализация
    new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    # сборка .siq
    if OUT_SIQ.exists():
        OUT_SIQ.unlink()
    with zipfile.ZipFile(OUT_SIQ, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("content.xml", new_xml)
        z.writestr("[Content].xml", new_xml)
        if qm is not None:
            z.writestr("quality.marker", qm)
        # Скрытый старт квеста: обычный файл в ZIP, который SIGame игнорирует,
        # а игрок находит, переименовав .siq в .zip и распаковав.
        z.writestr("START.txt", quest_start_text())
        for name, data in media.items():
            z.writestr(name, data)

    print(f"\nГотово: {OUT_SIQ.name}  ({OUT_SIQ.stat().st_size} байт)")
    print(f"медиа в пакете: {len(media)} файлов")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
