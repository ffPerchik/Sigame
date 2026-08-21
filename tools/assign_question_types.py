#!/usr/bin/env python3
"""Расставляет специальные типы вопросов в раундах пакета SIGame.

В каждом обычном раунде остаются простые вопросы и добавляется минимум по одному:
stake, secret, secretPublicPrice, secretNoQuestion, noRisk, forAll и stakeAll.
Раунд «Не спиздил, а адаптировал» и финальный раунд не изменяются.
"""
from __future__ import annotations

import argparse
import math
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = "https://github.com/VladimirKhil/SI/blob/master/assets/siq_5.xsd"
ET.register_namespace("", NS)

EXCLUDED_ROUNDS = {"Не спиздил, а адаптировал"}
SPECIAL_TYPES = (
    "stake",
    "secret",
    "secretPublicPrice",
    "secretNoQuestion",
    "noRisk",
    "forAll",
    "stakeAll",
)
SECRET_TYPES = {"secret", "secretPublicPrice", "secretNoQuestion"}
XML_FILES = {"content.xml", "[Content].xml"}


def q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def question_type(question: ET.Element) -> str:
    """Возвращает явный тип; отсутствие типа означает simple."""
    return question.get("type") or "simple"


def _round_questions(round_element: ET.Element) -> list[tuple[ET.Element, list[ET.Element]]]:
    result = []
    themes = round_element.find(q("themes"))
    if themes is None:
        return result
    for theme in themes.findall(q("theme")):
        questions_element = theme.find(q("questions"))
        questions = questions_element.findall(q("question")) if questions_element is not None else []
        if questions:
            result.append((theme, questions))
    return result


def _price_range(theme_questions: list[tuple[ET.Element, list[ET.Element]]]) -> tuple[int, int, int]:
    prices = sorted({
        int(question.get("price", "0"))
        for _, questions in theme_questions
        for question in questions
        if int(question.get("price", "0")) > 0
    })
    if not prices:
        return 100, 100, 0
    if len(prices) == 1:
        return prices[0], prices[0], 0
    differences = [b - a for a, b in zip(prices, prices[1:]) if b > a]
    step = math.gcd(*differences) if differences else 0
    return prices[0], prices[-1], step


def _remove_param(params: ET.Element, name: str) -> None:
    for param in list(params.findall(q("param"))):
        if param.get("name") == name:
            params.remove(param)


def _prepend_params(params: ET.Element, elements: list[ET.Element]) -> None:
    for element in reversed(elements):
        params.insert(0, element)


def _simple_param(name: str, value: str) -> ET.Element:
    element = ET.Element(q("param"), {"name": name})
    element.text = value
    return element


def _number_set_param(minimum: int, maximum: int, step: int) -> ET.Element:
    element = ET.Element(q("param"), {"name": "price", "type": "numberSet"})
    ET.SubElement(
        element,
        q("numberSet"),
        {"minimum": str(minimum), "maximum": str(maximum), "step": str(step)},
    )
    return element


def _ensure_secret_parameters(
    question: ET.Element,
    type_name: str,
    theme_name: str,
    price_range: tuple[int, int, int],
) -> None:
    params = question.find(q("params"))
    if params is None:
        params = ET.Element(q("params"))
        question.insert(0, params)
    names = {param.get("name") for param in params.findall(q("param"))}
    minimum, maximum, step = price_range
    missing = []
    if type_name != "secretNoQuestion" and "theme" not in names:
        missing.append(_simple_param("theme", theme_name))
    if "price" not in names:
        missing.append(_number_set_param(minimum, maximum, step))
    if "selectionMode" not in names:
        missing.append(_simple_param("selectionMode", "exceptCurrent"))
    _prepend_params(params, missing)


def set_question_type(
    question: ET.Element,
    type_name: str,
    theme_name: str,
    price_range: tuple[int, int, int],
) -> None:
    """Назначает тип и добавляет обязательные параметры секретных вопросов."""
    question.set("type", type_name)
    params = question.find(q("params"))
    if params is None:
        params = ET.Element(q("params"))
        question.insert(0, params)

    for parameter_name in ("theme", "price", "selectionMode"):
        _remove_param(params, parameter_name)

    if type_name not in SECRET_TYPES:
        return

    minimum, maximum, step = price_range
    secret_params = [
        _number_set_param(minimum, maximum, step),
        _simple_param("selectionMode", "exceptCurrent"),
    ]
    if type_name != "secretNoQuestion":
        secret_params.insert(0, _simple_param("theme", theme_name))
    _prepend_params(params, secret_params)


def apply_question_types(root: ET.Element) -> dict[str, dict[str, tuple[str, int]]]:
    """Изменяет XML и возвращает {раунд: {тип: (тема, цена)}}."""
    assignments: dict[str, dict[str, tuple[str, int]]] = {}
    rounds = root.find(q("rounds"))
    if rounds is None:
        raise ValueError("В content.xml нет секции rounds")

    for round_element in rounds.findall(q("round")):
        round_name = round_element.get("name", "")
        if round_name in EXCLUDED_ROUNDS or round_element.get("type") == "final":
            continue

        theme_questions = _round_questions(round_element)
        if not theme_questions:
            continue
        question_count = sum(len(questions) for _, questions in theme_questions)
        if question_count < len(SPECIAL_TYPES) + 1:
            raise ValueError(
                f"В раунде «{round_name}» недостаточно вопросов: {question_count}"
            )

        price_range = _price_range(theme_questions)
        round_assignments: dict[str, tuple[str, int]] = {}
        theme_count = len(theme_questions)

        # Первый проход берёт последний вопрос каждой темы, второй — предпоследний.
        # Так спецвопросы распределены по темам, а не собраны в одном месте.
        for index, type_name in enumerate(SPECIAL_TYPES):
            theme_index = index % theme_count
            depth = index // theme_count + 1
            theme, questions = theme_questions[theme_index]
            question = questions[-min(depth, len(questions))]
            set_question_type(question, type_name, theme.get("name", "Секрет"), price_range)
            round_assignments[type_name] = (
                theme.get("name", ""),
                int(question.get("price", "0")),
            )

        # Уже существующие секретные вопросы сохраняем на месте, но дополняем
        # обязательными параметрами, если старый пакет их не содержал.
        for theme, questions in theme_questions:
            for question in questions:
                existing_type = question_type(question)
                if existing_type in SECRET_TYPES:
                    _ensure_secret_parameters(
                        question,
                        existing_type,
                        theme.get("name", "Секрет"),
                        price_range,
                    )

        assignments[round_name] = round_assignments

    return assignments


def validate_question_types(root: ET.Element) -> None:
    rounds = root.find(q("rounds"))
    if rounds is None:
        raise ValueError("В content.xml нет секции rounds")

    for round_element in rounds.findall(q("round")):
        round_name = round_element.get("name", "")
        questions = [
            question
            for _, theme_questions in _round_questions(round_element)
            for question in theme_questions
        ]
        explicit_types = {question_type(question) for question in questions}

        if round_name in EXCLUDED_ROUNDS or round_element.get("type") == "final":
            continue

        required = {"simple", *SPECIAL_TYPES}
        missing = required - explicit_types
        if missing:
            raise ValueError(
                f"В раунде «{round_name}» отсутствуют типы: {', '.join(sorted(missing))}"
            )

        for question in questions:
            if question_type(question) not in SECRET_TYPES:
                continue
            params = question.find(q("params"))
            names = {param.get("name") for param in params.findall(q("param"))} if params is not None else set()
            required_params = {"price", "selectionMode"}
            if question_type(question) != "secretNoQuestion":
                required_params.add("theme")
            if not required_params <= names:
                raise ValueError(
                    f"У типа {question_type(question)} в раунде «{round_name}» не хватает параметров"
                )


def update_package(package_path: Path) -> dict[str, dict[str, tuple[str, int]]]:
    """Обновляет SIQ/ZIP атомарно, сохраняя все медиа и служебные файлы."""
    if not package_path.is_file():
        raise FileNotFoundError(package_path)

    with zipfile.ZipFile(package_path, "r") as source:
        entries = [(info, source.read(info.filename)) for info in source.infolist()]

    content = next((data for info, data in entries if info.filename == "content.xml"), None)
    if content is None:
        raise ValueError(f"В {package_path} отсутствует content.xml")

    root = ET.fromstring(content)
    assignments = apply_question_types(root)
    validate_question_types(root)
    new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    with tempfile.NamedTemporaryFile(
        dir=package_path.parent,
        prefix=package_path.stem + "-",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)

    try:
        with zipfile.ZipFile(temporary_path, "w") as target:
            for info, data in entries:
                target.writestr(info, new_xml if info.filename in XML_FILES else data)
        temporary_path.replace(package_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return assignments


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "package",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "zengame.siq",
        help="путь к пакету SIQ (по умолчанию zengame.siq в корне репозитория)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    assignments = update_package(args.package)
    for round_name, types in assignments.items():
        print(round_name)
        for type_name, (theme, price) in types.items():
            print(f"  {type_name}: {theme}, {price}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
