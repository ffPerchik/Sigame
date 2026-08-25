#!/usr/bin/env python3
"""
Сборка финального пакета SIGame (формат v5) → zengame.siq.

Что делает:
  1. Читает content.xml и медиа прямо из source.siq (без распаковки на диск).
  2. Раскладывает 27 исходных тем по 5 раундам (Раунд 1 — полностью
     тематический «География») + добавляет ФИНАЛ (type="final").
  3. Переименовывает ВСЕ темы в вид «<смайлик><название>» (смайлики уникальны).
  4. Добавляет свои темы: «Армянская еда», «BTS» и финальную тему со
     стеганографической фоткой (final_photo.png — обычный пейзаж, внутри LSB-послание).
  5. Регенерирует <files>-манифест для добавленных картинок.
  6. Кладёт скрытый START.txt (SIGame игнорирует) — следующий слой квеста.

Запуск:
    python3 tools/build_v5.py
"""
from __future__ import annotations

import datetime
import hashlib
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from .assign_question_types import apply_question_types, validate_question_types
except ImportError:  # `python tools/build_v5.py`
    from assign_question_types import apply_question_types, validate_question_types

NS = "https://github.com/VladimirKhil/SI/blob/master/assets/siq_5.xsd"
ET.register_namespace("", NS)

ROOT = Path(__file__).resolve().parent.parent
ZEN = ROOT / "source.siq"            # исходная заготовка (27 тем + медиа)
MY_IMAGES = ROOT / "content" / "Images"
OUT_SIQ = ROOT / "zengame.siq"       # финальный пакет


def q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


# ---- переименование тем: индекс исходной темы -> «<смайлик><название>» (смайлики уникальны) ----
RENAME = {
    0:  "🎬 Кинчик",
    1:  "📷 Картинка с фразой",
    2:  "🙈 Случайные вопросы",
    3:  "📺 Мультики",
    4:  "🏙 Столицы стран",
    5:  "🧅 Шрек",
    6:  "🏺 Античность",
    7:  "🧱 Построили в майнкрафт",
    8:  "🎨 Хреново нарисовали мем",
    9:  "🎤 Продолжи песню",
    10: "💑 Вторая половинка",
    11: "🎲 Рандом вопрос",
    12: "🦝 Тему захватили Еноты",
    13: "🧸 Всё о мультиках",
    14: "🎧 Лучшие песни Shazam 2025",
    15: "🔤 Анаграммы городов",
    16: "🧭 Страна по президенту",
    17: "🎯 Рандом вопрос",
    18: "👘 Женский косплей",
    19: "🚩 А ты знаешь флаги?",
    20: "🧮 Рандом вопросы",
    21: "🌍 Из какой страны?",
    22: "🔎 Задачи на внимательность",
    23: "📜 Средневековые афиши",
    24: "⚖ 50/50",
    25: "💰 Валюта",
    26: "❓ Случайный вопрос",
}


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
    th = ET.Element(q("theme"), {"name": "🍽 Армянская еда"})
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
    th = ET.Element(q("theme"), {"name": "💜 BTS"})
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


def build_final_theme():
    """Финальная тема: обычный пейзаж со спрятанным (LSB) посланием.
    Вопрос учит слову «стеганография» — намёк извлечь скрытое из картинки."""
    th = ET.Element(q("theme"), {"name": "🔑 Финал"})
    qs = ET.SubElement(th, q("questions"))
    items = [
        ("text", "Финал. Перед вами обычный пейзаж. Но внутри изображения спрятано послание. "
                 "Назовите способ скрытия сообщений внутри картинок."),
        ("image", "final_photo.png"),
    ]
    answers = ["стеганография", "стеганографія", "steganography"]
    qs.append(make_question(0, items, answers))
    return th


INJECTORS = {"armenian": build_armenian_theme, "bts": build_bts_theme, "final": build_final_theme}

# ---- план раундов: (название, тип, [индексы тем], [инъекции]) ----
ROUND_PLAN = [
    ("Раунд 1 — География",            None,    [4, 15, 16, 19, 21, 25], []),
    ("Раунд 2 — Кино, мультики, мемы", None,    [0, 1, 3, 5, 13, 8],    []),
    ("Раунд 3 — Музыка и стиль",       None,    [9, 14, 18, 10, 23],    []),
    ("Раунд 4 — Игры и головоломки",   None,    [7, 12, 22, 24, 6, 11], []),
    ("Раунд 5 — Микс + бонус",         None,    [2, 17, 20, 26],         ["armenian", "bts"]),
    ("Финал",                          "final", [],                      ["final"]),
]


def quest_start_text() -> str:
    """Точный текст START.txt, согласованный с содержимым готового пакета."""
    message = (
        "0J/QntCX0JTQoNCQ0JLQm9Cv0K4sINGC0Ysg0L3QtSDQsdC10LfQvdCw0LTRkdC20LXQvSwg"
        "QVJHVVMg0LLQv9C10YfQsNGC0LvRkdC9LiDQndC40LbQtSDQutC+0LQsINC60L7RgtC+0YDR"
        "i9C5INC00LDRgdGCINGC0LXQsdC1INC00L7RgdGC0YPQvy4g0JTQsNC70YzRiNC1INCa0JDQ"
        "ltCU0KvQmSDQodCQ0Jwg0JfQkCDQodCV0JHQry4g0KHQm9CV0JTQo9Cu0KnQmNCZINCh0JvQ"
        "ntCZINCh0J/QoNCv0KLQkNCdINCT0JvQo9CR0JbQlTog0JIg0JrQkNCg0KLQmNCd0JrQkNCl"
        "LCDQkiDQntCi0JLQldCi0JDQpSwg0JIg0KjQmNCk0KDQkNCl0KXQntCg0J7QqNCeINCh0J/Q"
        "oNCv0KLQkNCd0J3QntCVIOKAlCDQpdCe0KDQntCo0J4g0J3QkNCZ0JTQgdCd0J3QntCVLg=="
    )
    key = "QVJHVVMxMDAx"
    return (
        "   ╔══════════════════════════════════════════════╗\n"
        "   ║   ВЫ НАШЛИ НАЧАЛО                                          ║\n"
        "   ╚══════════════════════════════════════════════╝\n"
        "\n"
        "   Тот, кто читает это, — перестал быть просто игроком.\n"
        "\n"
        "   Дальше каждый сам за себя.\n"
        "\n"
        "   Первое послание закодировано. Расшифруй:\n"
        "\n"
        f"{message}\n"
        "\n"
        "   Та же кодировка:\n"
        "\n"
        f"{key}\n"
        "\n"
        "   — хороший поиск вознаграждается.\n"
    )


def update_start_text_in_package(package_path: Path = OUT_SIQ) -> None:
    """Обновляет только START.txt, не пересобирая раунды и медиа пакета."""
    with zipfile.ZipFile(package_path, "r") as source:
        entries = [(info, source.read(info.filename)) for info in source.infolist()]

    with tempfile.NamedTemporaryFile(
        dir=package_path.parent,
        prefix=package_path.stem + "-start-",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)

    try:
        with zipfile.ZipFile(temporary_path, "w") as target:
            found = False
            for info, data in entries:
                if info.filename == "START.txt":
                    data = quest_start_text().encode("utf-8")
                    found = True
                target.writestr(info, data)
            if not found:
                target.writestr("START.txt", quest_start_text())
        temporary_path.replace(package_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def main() -> int:
    if not ZEN.exists():
        print(f"Исходный пакет не найден: {ZEN}", file=sys.stderr)
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

    used = set()
    for _, _, idxs, _ in ROUND_PLAN:
        used.update(idxs)
    missing = set(range(len(theme_list))) - used
    if missing:
        print(f"⚠ темы без раунда (индексы): {sorted(missing)}", file=sys.stderr)

    by_idx = {i: t for i, t in enumerate(theme_list)}

    rounds_el = root.find(f"{q('rounds')}")
    rounds_el.remove(orig_round)
    for rname, rtype, idxs, inject in ROUND_PLAN:
        attrs = {"name": rname}
        if rtype:
            attrs["type"] = rtype
        r = ET.SubElement(rounds_el, q("round"), attrs)
        ths = ET.SubElement(r, q("themes"))
        for i in idxs:
            el = by_idx[i]
            if i in RENAME:
                el.set("name", RENAME[i])
            ths.append(el)
        for inj in inject:
            ths.append(INJECTORS[inj]())
        n_themes = len(ths)
        n_qs = sum(len(t.find(f"{q('questions')}").findall(f"{q('question')}"))
                   for t in ths)
        print(f"  {rname}{' ['+rtype+']' if rtype else ''}: тем={n_themes}, вопросов={n_qs}")

    type_assignments = apply_question_types(root)
    validate_question_types(root)
    print("специальные типы вопросов:")
    for round_name, assigned_types in type_assignments.items():
        print(f"  {round_name}: {', '.join(assigned_types)}")

    # имя/дата пакета
    root.set("name", "Zengame")
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

    new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    if OUT_SIQ.exists():
        OUT_SIQ.unlink()
    with zipfile.ZipFile(OUT_SIQ, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("content.xml", new_xml)
        z.writestr("[Content].xml", new_xml)
        if qm is not None:
            z.writestr("quality.marker", qm)
        # скрытый старт квеста (SIGame игнорирует лишние файлы в ZIP)
        z.writestr("START.txt", quest_start_text())
        for name, data in media.items():
            z.writestr(name, data)

    print(f"\nГотово: {OUT_SIQ.name}  ({OUT_SIQ.stat().st_size} байт)")
    print(f"медиа в пакете: {len(media)} файлов")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
