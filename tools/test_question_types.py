import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.assign_question_types import (
    EXCLUDED_ROUNDS,
    SECRET_TYPES,
    SPECIAL_TYPES,
    apply_question_types,
    q,
    question_type,
    validate_question_types,
)

PACKAGE = REPO_ROOT / "zengame.siq"


def load_root() -> ET.Element:
    with zipfile.ZipFile(PACKAGE) as package:
        return ET.fromstring(package.read("content.xml"))


def questions(round_element: ET.Element) -> list[ET.Element]:
    return list(round_element.iter(q("question")))


class QuestionTypesTests(unittest.TestCase):
    def test_every_regular_round_has_every_category(self):
        root = load_root()
        validate_question_types(root)

        for round_element in root.find(q("rounds")).findall(q("round")):
            round_name = round_element.get("name", "")
            if round_name in EXCLUDED_ROUNDS or round_element.get("type") == "final":
                continue
            counts = Counter(question_type(question) for question in questions(round_element))
            self.assertGreater(counts["simple"], 0, round_name)
            for type_name in SPECIAL_TYPES:
                self.assertGreater(counts[type_name], 0, f"{round_name}: {type_name}")

    def test_special_questions_are_not_always_last_in_theme(self):
        root = load_root()
        for round_element in root.find(q("rounds")).findall(q("round")):
            round_name = round_element.get("name", "")
            if round_name in EXCLUDED_ROUNDS or round_element.get("type") == "final":
                continue
            special_questions = []
            last_questions = set()
            for theme in round_element.iter(q("theme")):
                theme_questions = list(theme.iter(q("question")))
                if theme_questions:
                    last_questions.add(id(theme_questions[-1]))
                special_questions.extend(
                    question
                    for question in theme_questions
                    if question_type(question) in SPECIAL_TYPES
                )
            self.assertTrue(
                any(id(question) not in last_questions for question in special_questions),
                f"В раунде «{round_name}» все спецтипы стоят последними",
            )

    def test_seed_is_reproducible_and_changeable(self):
        first = load_root()
        second = load_root()
        third = load_root()
        assignment_a = apply_question_types(first, seed=12345)
        assignment_b = apply_question_types(second, seed=12345)
        assignment_c = apply_question_types(third, seed=54321)
        self.assertEqual(assignment_a, assignment_b)
        self.assertNotEqual(assignment_a, assignment_c)
        apply_question_types(first, seed=12345)
        self.assertEqual(ET.tostring(first), ET.tostring(second))

    def test_excluded_and_final_rounds_are_not_touched(self):
        root = load_root()
        protected = {
            round_element.get("name", ""): ET.tostring(round_element)
            for round_element in root.find(q("rounds")).findall(q("round"))
            if round_element.get("name", "") in EXCLUDED_ROUNDS
            or round_element.get("type") == "final"
        }

        apply_question_types(root)

        after = {
            round_element.get("name", ""): ET.tostring(round_element)
            for round_element in root.find(q("rounds")).findall(q("round"))
            if round_element.get("name", "") in protected
        }
        self.assertEqual(after, protected)

    def test_secret_questions_have_required_parameters(self):
        root = load_root()
        for question in root.iter(q("question")):
            type_name = question_type(question)
            if type_name not in SECRET_TYPES:
                continue
            params = question.find(q("params"))
            by_name = {param.get("name"): param for param in params.findall(q("param"))}
            self.assertIn("price", by_name)
            self.assertIn("selectionMode", by_name)
            self.assertEqual(by_name["selectionMode"].text, "exceptCurrent")
            number_set = by_name["price"].find(q("numberSet"))
            self.assertIsNotNone(number_set)
            if type_name != "secretNoQuestion":
                self.assertIn("theme", by_name)

    def test_content_copies_are_equal(self):
        with zipfile.ZipFile(PACKAGE) as package:
            self.assertEqual(package.read("content.xml"), package.read("[Content].xml"))


if __name__ == "__main__":
    unittest.main()
