#!/usr/bin/env python3
"""
Инкрементальные правки пакета zengame.siq (вход и выход — сам zengame.siq).

Применяет:
  1. Рост цен по раундам: каждый «игровой» раунд получает базу base = level*100,
     шаг 100 (вопрос i стоит base + i*100). Level растёт по порядку раундов.
     Пустые раунды (без вопросов) пропускаются и не трогаются.
  2. Наполнение Финала: к финальному раунду (type="final") добавляются
     темы-обманки, чтобы стегано-подсказка не выделялась (1 тема → несколько).

Запуск:
    python3 tools/edit_zengame.py
"""
from __future__ import annotations
import os, zipfile
import xml.etree.ElementTree as ET

NS = "https://github.com/VladimirKhil/SI/blob/master/assets/siq_5.xsd"
ET.register_namespace("", NS)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "zengame.siq")


def q(t): return f"{{{NS}}}{t}"


def make_text_question(price, text, answers):
    qel = ET.Element(q("question"), {"price": str(price)})
    params = ET.SubElement(qel, q("params"))
    p = ET.SubElement(params, q("param"), {"name": "question", "type": "content"})
    item = ET.SubElement(p, q("item"))
    item.text = text
    right = ET.SubElement(qel, q("right"))
    for a in answers:
        ET.SubElement(right, q("answer")).text = a
    return qel


def build_decoy_theme(emoji_name, text, answers):
    th = ET.Element(q("theme"), {"name": emoji_name})
    qs = ET.SubElement(th, q("questions"))
    qs.append(make_text_question(0, text, answers))  # цена выставится эскалацией
    return th


# Темы-обманки для Финала (по одному текстовому вопросу; уникальные смайлики)
DECOYS = [
    ("🧠 Логика", "Что становится мокрее, пока сушит?", ["Полотенце"]),
    ("🔬 Наука", "Какой газ составляет около 78% воздуха атмосферы Земли?", ["Азот"]),
    ("🎭 Цитаты", "«Я вернусь» (I'll be back) — коронная фраза какого киногероя?",
     ["Терминатор"]),
    ("⚽ Спорт", "Сколько игроков одной команды одновременно на поле в футболе?",
     ["11", "Одиннадцать", "одиннадцать"]),
]


def theme_questions(theme):
    qel = theme.find(q("questions"))
    return qel.findall(q("question")) if qel is not None else []


def main():
    with zipfile.ZipFile(PKG) as z:
        entries = [(zi, z.read(zi.filename)) for zi in z.infolist()]
    content = next(d for n, d in [(zi.filename, d) for zi, d in entries] if n == "content.xml")
    root = ET.fromstring(content)
    rounds = root.find(q("rounds")).findall(q("round"))

    # 1) Наполнить Финал обманками
    for r in rounds:
        if r.attrib.get("type") == "final":
            themes_el = r.find(q("themes"))
            if themes_el is None:
                themes_el = ET.SubElement(r, q("themes"))
            existing = {t.attrib["name"] for t in themes_el.findall(q("theme"))}
            added = 0
            for name, text, ans in DECOYS:
                if name not in existing:
                    themes_el.append(build_decoy_theme(name, text, ans))
                    added += 1
            print(f"Финал: добавлено тем-обманок: {added} "
                  f"(всего тем теперь: {len(themes_el.findall(q('theme')))})")

    # 2) Эскалация цен по раундам
    print("\nЭскалация цен:")
    level = 0
    for ri, r in enumerate(rounds):
        themes = r.find(q("themes")).findall(q("theme")) if r.find(q("themes")) is not None else []
        total_q = sum(len(theme_questions(t)) for t in themes)
        is_final = r.attrib.get("type") == "final"
        if total_q == 0 and not is_final:
            print(f"  R{ri} {r.attrib.get('name')!r}: пустой раунд — пропускаю")
            continue
        level += 1
        base = level * 100
        for t in themes:
            for i, qq in enumerate(theme_questions(t)):
                qq.set("price", str(base + i * 100))
        pr = []
        for t in themes:
            ps = [int(qq.attrib.get("price", 0)) for qq in theme_questions(t)]
            if ps:
                pr.append(f"{t.attrib['name']}:{min(ps)}-{max(ps)}")
        print(f"  R{ri} {r.attrib.get('name')!r} (level {level}, base {base}): {pr}")

    new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    tmp = PKG + ".new"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for zi, data in entries:
            if zi.filename == "content.xml":
                z.writestr("content.xml", new_xml)
            elif zi.filename == "[Content].xml":
                z.writestr("[Content].xml", new_xml)
            else:
                z.writestr(zi, data)
    os.replace(tmp, PKG)
    print(f"\nГотово: zengame.siq ({os.path.getsize(PKG)} байт)")


if __name__ == "__main__":
    main()
