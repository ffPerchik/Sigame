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
