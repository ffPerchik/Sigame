#!/usr/bin/env python3
"""
Заполнить раунд R2 «Не спиздил, а адаптировал» тремя адаптированными телешоу:
  📊 Сто к одному  (опрос — угадать топ-ответ)
  🏃 Погоня        (ведущий = Гончий, игрок убегает)
  💸 Десять миллионов (ставка на 1 из 4 вариантов)
Цены выставит tools/edit_zengame.py (эскалация). Вход и выход — zengame.siq.
"""
from __future__ import annotations
import os, zipfile
import xml.etree.ElementTree as ET

NS = "https://github.com/VladimirKhil/SI/blob/master/assets/siq_5.xsd"
ET.register_namespace("", NS)
ROUND_NAME = "Не спиздил, а адаптировал"
PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "zengame.siq")


def q(t): return f"{{{NS}}}{t}"


def _info(parent, comment):
    if comment:
        info = ET.SubElement(parent, q("info"))
        ET.SubElement(info, q("comments")).text = comment


def text_question(price, text, answers, comment=None):
    qel = ET.Element(q("question"), {"price": str(price)})
    _info(qel, comment)
    params = ET.SubElement(qel, q("params"))
    p = ET.SubElement(params, q("param"), {"name": "question", "type": "content"})
    ET.SubElement(p, q("item")).text = text
    right = ET.SubElement(qel, q("right"))
    for a in answers:
        ET.SubElement(right, q("answer")).text = a
    return qel


def select_question(price, text, options, right_letter, comment=None):
    qel = ET.Element(q("question"), {"price": str(price)})
    _info(qel, comment)
    params = ET.SubElement(qel, q("params"))
    pq = ET.SubElement(params, q("param"), {"name": "question", "type": "content"})
    ET.SubElement(pq, q("item")).text = text
    ET.SubElement(params, q("param"), {"name": "answerType"}).text = "select"
    grp = ET.SubElement(params, q("param"), {"name": "answerOptions", "type": "group"})
    for letter in ["A", "B", "C", "D"]:
        sp = ET.SubElement(grp, q("param"), {"name": letter, "type": "content"})
        ET.SubElement(sp, q("item")).text = options[letter]
    right = ET.SubElement(qel, q("right"))
    ET.SubElement(right, q("answer")).text = right_letter
    return qel


def theme(name, comment, questions):
    th = ET.Element(q("theme"), {"name": name})
    _info(th, comment)
    qs = ET.SubElement(th, q("questions"))
    for qel in questions:
        qs.append(qel)
    return th


# ---------- 📊 Сто к одному ----------
sto = theme("📊 Сто к одному",
    "Правила «Сто к одному»: ведущий открывает вопрос-опрос 100 человек. "
    "Игроки по очереди называют варианты. В комментариях ведущего — полный топ "
    "(1=самый частый). Очки можно давать по месту ответа.",
    [
        text_question(100, "Опрос 100 человек: «Назовите самого популярного домашнего питомца». Какой ответ на 1-м месте?",
            ["Кошка", "Кот"], "ТОП: 1.Кошка 2.Собака 3.Попугай 4.Рыбки 5.Хомяк 6.Черепаха"),
        text_question(200, "Опрос: «Куда россияне чаще всего ездят отдыхать за границу?» Назовите топ-1.",
            ["Турция"], "ТОП: 1.Турция 2.Абхазия 3.Грузия 4.Египет 5.ОАЭ 6.Таиланд"),
        text_question(300, "Опрос: «Что вы берёте с собой на пляж?» Самый частый ответ?",
            ["Полотенце"], "ТОП: 1.Полотенце 2.Крем от солнца 3.Вода 4.Солнечные очки 5.Купальник/плавки 6.Шляпа"),
        text_question(400, "Опрос: «Какой новогодний фильм/передачу включают чаще всего?» Топ-1?",
            ["Ирония судьбы", "Ирония судьбы, или С лёгким паром"], "ТОП: 1.Ирония судьбы 2.Один дома 3.Гарри Поттер 4.Ёлки 5.Голубой огонёк 6.Хроники Нарнии"),
        text_question(500, "Опрос: «Что люди делают в выходные чаще всего?» Назовите топ-1.",
            ["Спать", "Отсыпаться"], "ТОП: 1.Спать 2.Гулять 3.Смотреть кино 4.Ехать на дачу 5.Встречаться с друзьями 6.Убираться"),
        text_question(600, "Опрос: «Какой фрукт вы едите чаще всего?» Самый популярный?",
            ["Яблоко"], "ТОП: 1.Яблоко 2.Банан 3.Апельсин 4.Груша 5.Мандарин 6.Виноград"),
    ])

# ---------- 🏃 Погоня ----------
pogo = theme("🏃 Погоня",
    "Правила «Погоня» (The Chase): ведущий — «Гончий», сильный преследователь. "
    "Игрок отвечает на вопрос; верно — отрывается на шаг. Затем ведущий отвечает "
    "за Гончего (используй комментарий к вопросу как подсказку Гончего); если верно — "
    "догоняет. Догнал — игрок вылетает. Цель — дойти до финиша.",
    [
        text_question(100, "Самый распространённый химический элемент во Вселенной?",
            ["Водород"], "Гончий знает: водород — около 75% массы Вселенной."),
        text_question(200, "Столица Австралии (это не Сидней и не Мельбурн)?",
            ["Канберра"], "Ловушка для Гончего: многие путают с Сиднеем."),
        text_question(300, "В каком году Юрий Гагарин совершил первый полёт в космос?",
            ["1961"], "12 апреля 1961 года."),
        text_question(400, "Кто написал картину «Звёздная ночь»?",
            ["Ван Гог", "Винсент Ван Гог", "Винсент ван Гог"], "Винсент Ван Гог, 1889."),
        text_question(500, "Сколько костей у взрослого человека?",
            ["206"], "У младенца около 300 — потом срастаются до 206."),
        text_question(600, "Самая высокая гора в мире над уровнем моря?",
            ["Эверест", "Джомолунгма", "Сагарматха"], "8848 м. Ловушка: от основания — Мауна-Кеа."),
    ])

# ---------- 💸 Десять миллионов ----------
des = theme("💸 Десять миллионов",
    "Правила «Десять миллионов» (Million Pound Drop): у игрока виртуальная сумма. "
    "Ведущий читает вопрос с 4 вариантами. Игрок «ставит» деньги на ответ (можно "
    "дробить между вариантами — скажи ведущему как). Деньги на неверном варианте "
    "сгорают. Цель — сохранить сумму до конца.",
    [
        select_question(100, "Сколько сторон у правильного шестиугольника?",
            {"A": "5", "B": "6", "C": "7", "D": "8"}, "B"),
        select_question(200, "Какая планета ближе всего к Солнцу?",
            {"A": "Венера", "B": "Земля", "C": "Меркурий", "D": "Марс"}, "C"),
        select_question(300, "Кто написал роман «Война и мир»?",
            {"A": "Достоевский", "B": "Толстой", "C": "Тургенев", "D": "Гоголь"}, "B"),
        select_question(400, "Столица Канады?",
            {"A": "Торонто", "B": "Монреаль", "C": "Ванкувер", "D": "Оттава"}, "D",
            "Ловушка: многие называют Торонто."),
        select_question(500, "Сколько игроков одной команды одновременно на льду в хоккее?",
            {"A": "5", "B": "6", "C": "7", "D": "11"}, "B",
            "5 полевых игроков + вратарь = 6."),
        select_question(600, "В каких единицах измеряется частота?",
            {"A": "Амперах", "B": "Герцах", "C": "Ваттах", "D": "Омах"}, "B"),
    ])

NEW_THEMES = [sto, pogo, des]


def main():
    with zipfile.ZipFile(PKG) as z:
        entries = [(zi, z.read(zi.filename)) for zi in z.infolist()]
    content = next(d for n, d in [(zi.filename, d) for zi, d in entries] if n == "content.xml")
    root = ET.fromstring(content)
    rounds = root.find(q("rounds")).findall(q("round"))
    target = None
    for r in rounds:
        if r.attrib.get("name") == ROUND_NAME:
            target = r
            break
    if target is None:
        raise SystemExit(f"Раунд «{ROUND_NAME}» не найден")
    themes_el = target.find(q("themes"))
    if themes_el is None:
        themes_el = ET.SubElement(target, q("themes"))
    else:
        for t in list(themes_el):
            themes_el.remove(t)        # убрать пустую тему-заглушку
    existing_names = {t.attrib["name"] for t in root.iter(q("theme"))}
    for th in NEW_THEMES:
        if th.attrib["name"] not in existing_names:
            themes_el.append(th)
            print("добавлена тема:", th.attrib["name"],
                  f"({len(th.find(q('questions')).findall(q('question')))} вопр.)")
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
    print(f"\nzengame.siq обновлён ({os.path.getsize(PKG)} байт). Цены выставит edit_zengame.py.")


if __name__ == "__main__":
    main()
