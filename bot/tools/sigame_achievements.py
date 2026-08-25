#!/usr/bin/env python3
"""Подсчёт ачивок и подсказок по журналу SIGame.

Поддерживаются:
* TXT-журнал Steam/SIOnline с выбором вопросов и изменениями счёта;
* HTML-журнал классической настольной SIGame.

Зависимостей вне стандартной библиотеки Python нет.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


BOT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BOT_ROOT.parent
REPORTS_DIR = BOT_ROOT / "quest" / "achievements"

MIN_ACCURACY_ATTEMPTS = 10
TARGET_SCORE = 6767
HIGH_ROLLER_DELTA = 2000
COMEBACK_FLOOR = -1000


@dataclass
class RawAnswer:
    sequence: int
    player_index: int
    text: str


@dataclass
class RawOutcome:
    sequence: int
    player_index: int
    delta: int


@dataclass(frozen=True)
class QuestionContext:
    round_name: str
    theme: str
    price: int


@dataclass
class Outcome:
    sequence: int
    player: str
    delta: int
    kind: str = "answer"  # answer | manual
    answer: str | None = None
    round_name: str | None = None
    theme: str | None = None
    question_price: int | None = None


@dataclass
class PlayerMetrics:
    name: str
    final_score: int = 0
    right_count: int = 0
    wrong_count: int = 0
    right_total: int = 0
    wrong_total: int = 0
    min_score: int = 0
    max_score: int = 0
    max_gain: int = 0
    max_loss: int = 0
    max_right_streak: int = 0
    max_wrong_streak: int = 0
    returned_to_zero: bool = False
    manual_change_count: int = 0
    manual_total: int = 0
    answers: list[str] = field(default_factory=list)
    net_by_theme: dict[str, int] = field(default_factory=dict)
    positive_by_theme: dict[str, int] = field(default_factory=dict)
    net_by_round: dict[str, int] = field(default_factory=dict)
    right_by_theme: dict[str, int] = field(default_factory=dict)
    wrong_by_theme: dict[str, int] = field(default_factory=dict)
    right_by_round: dict[str, int] = field(default_factory=dict)
    wrong_by_round: dict[str, int] = field(default_factory=dict)
    right_by_price: dict[int, int] = field(default_factory=dict)
    wrong_by_price: dict[int, int] = field(default_factory=dict)

    @property
    def attempts(self) -> int:
        return self.right_count + self.wrong_count

    @property
    def accuracy(self) -> float | None:
        return self.right_count / self.attempts if self.attempts else None


@dataclass
class GameData:
    source: str
    players: dict[str, PlayerMetrics]
    outcomes: list[Outcome]
    round_names: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class Award:
    code: str
    title: str
    points: int
    evidence: str


class SIGameHTMLParser(HTMLParser):
    """Извлекает структурированные data-теги из официального HTML-журнала."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.player_names: dict[int, str] = {}
        self.answers: list[RawAnswer] = []
        self.outcomes: list[RawOutcome] = []
        self._sequence = 0
        self._span_stack: list[dict] = []
        self._next_answer_index: int | None = None

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "br":
            self._next_answer_index = None
            return

        if tag.lower() != "span":
            return

        data = {key.lower(): value or "" for key, value in attrs}
        data_tag = data.get("data-tag", "").lower()

        if data_tag == "gameinfo":
            for key, value in data.items():
                match = re.fullmatch(r"data-player-(\d+)", key)
                if match:
                    self.player_names[int(match.group(1))] = html.unescape(value).strip()

        if data_tag == "sumchange":
            try:
                player_index = int(data["data-playerindex"])
                delta = int(data["data-change"])
            except (KeyError, ValueError):
                pass
            else:
                self.outcomes.append(RawOutcome(self._next_sequence(), player_index, delta))

        classes = set(data.get("class", "").split())
        context: dict = {"kind": "other", "text": []}

        if "sr" in classes:
            player_class = next((item for item in classes if re.fullmatch(r"n\d+", item)), None)
            if player_class:
                context = {"kind": "speaker", "player_index": int(player_class[1:]), "text": []}
        elif "r" in classes and self._next_answer_index is not None:
            context = {"kind": "answer", "player_index": self._next_answer_index, "text": []}

        self._span_stack.append(context)

    def handle_data(self, data: str) -> None:
        for context in reversed(self._span_stack):
            if context["kind"] == "answer":
                context["text"].append(data)
                break

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "span" or not self._span_stack:
            return

        context = self._span_stack.pop()
        if context["kind"] == "speaker":
            self._next_answer_index = context["player_index"]
        elif context["kind"] == "answer":
            text = html.unescape("".join(context["text"])).strip()
            self.answers.append(RawAnswer(self._next_sequence(), context["player_index"], text))
            self._next_answer_index = None


def _build_game_from_raw(
    source: str,
    player_names: dict[int, str],
    raw_answers: list[RawAnswer],
    raw_outcomes: list[RawOutcome],
) -> GameData:
    indexes = set(player_names)
    indexes.update(item.player_index for item in raw_answers)
    indexes.update(item.player_index for item in raw_outcomes)

    names = {
        index: player_names.get(index) or f"Игрок {index + 1}"
        for index in sorted(indexes)
    }
    players = {name: PlayerMetrics(name=name) for name in names.values()}

    pending_answers: dict[int, list[str]] = defaultdict(list)
    outcomes: list[Outcome] = []
    all_events: list[tuple[int, str, RawAnswer | RawOutcome]] = [
        (item.sequence, "answer", item) for item in raw_answers
    ] + [
        (item.sequence, "outcome", item) for item in raw_outcomes
    ]

    for _, event_type, event in sorted(all_events, key=lambda item: item[0]):
        if event_type == "answer":
            assert isinstance(event, RawAnswer)
            pending_answers[event.player_index].append(event.text)
            players[names[event.player_index]].answers.append(event.text)
            continue

        assert isinstance(event, RawOutcome)
        answer = pending_answers[event.player_index].pop() if pending_answers[event.player_index] else None
        # Старые ответы без изменения счёта не должны приклеиваться к следующему вопросу.
        pending_answers[event.player_index].clear()
        outcomes.append(
            Outcome(
                sequence=event.sequence,
                player=names[event.player_index],
                delta=event.delta,
                answer=answer,
            )
        )

    _calculate_metrics(players, outcomes)
    warnings: list[str] = []
    if not raw_outcomes:
        warnings.append("В журнале нет изменений счёта; возможно, игра ещё не завершена или лог не сброшен на диск.")
    if not player_names:
        warnings.append("Не найден gameInfo: имена игроков восстановлены по индексам.")

    return GameData(source=source, players=players, outcomes=outcomes, warnings=warnings)


def _calculate_metrics(players: dict[str, PlayerMetrics], outcomes: list[Outcome]) -> None:
    scores = defaultdict(int)
    current_right_streak = defaultdict(int)
    current_wrong_streak = defaultdict(int)
    was_nonzero = defaultdict(bool)

    for outcome in sorted(outcomes, key=lambda item: item.sequence):
        player = players[outcome.player]
        scores[outcome.player] += outcome.delta
        player.final_score = scores[outcome.player]
        player.min_score = min(player.min_score, player.final_score)
        player.max_score = max(player.max_score, player.final_score)

        if outcome.delta > 0:
            player.max_gain = max(player.max_gain, outcome.delta)
        elif outcome.delta < 0:
            player.max_loss = max(player.max_loss, abs(outcome.delta))

        if player.final_score != 0:
            was_nonzero[outcome.player] = True
        elif was_nonzero[outcome.player]:
            player.returned_to_zero = True

        # Любые изменения счёта, включая ручные, влияют на результат темы и раунда.
        if outcome.theme and outcome.delta != 0:
            player.net_by_theme[outcome.theme] = player.net_by_theme.get(outcome.theme, 0) + outcome.delta
            if outcome.delta > 0:
                player.positive_by_theme[outcome.theme] = (
                    player.positive_by_theme.get(outcome.theme, 0) + outcome.delta
                )
        if outcome.round_name and outcome.delta != 0:
            player.net_by_round[outcome.round_name] = (
                player.net_by_round.get(outcome.round_name, 0) + outcome.delta
            )

        # Ручная корректировка учитывается в счёте, но не выдаётся за верный или
        # неверный ответ и не меняет серии ответов.
        if outcome.kind == "manual":
            player.manual_change_count += 1
            player.manual_total += outcome.delta
            continue

        if outcome.delta > 0:
            player.right_count += 1
            player.right_total += outcome.delta
            current_right_streak[outcome.player] += 1
            current_wrong_streak[outcome.player] = 0
        elif outcome.delta < 0:
            player.wrong_count += 1
            player.wrong_total += abs(outcome.delta)
            current_wrong_streak[outcome.player] += 1
            current_right_streak[outcome.player] = 0

        player.max_right_streak = max(player.max_right_streak, current_right_streak[outcome.player])
        player.max_wrong_streak = max(player.max_wrong_streak, current_wrong_streak[outcome.player])

        if outcome.theme:
            target = player.right_by_theme if outcome.delta > 0 else player.wrong_by_theme
            if outcome.delta != 0:
                target[outcome.theme] = target.get(outcome.theme, 0) + 1
        if outcome.round_name:
            target = player.right_by_round if outcome.delta > 0 else player.wrong_by_round
            if outcome.delta != 0:
                target[outcome.round_name] = target.get(outcome.round_name, 0) + 1
        if outcome.question_price is not None:
            target = player.right_by_price if outcome.delta > 0 else player.wrong_by_price
            if outcome.delta != 0:
                target[outcome.question_price] = target.get(outcome.question_price, 0) + 1


def parse_html_log(path: Path, content: str) -> GameData:
    parser = SIGameHTMLParser()
    parser.feed(content)
    parser.close()
    return _build_game_from_raw(str(path), parser.player_names, parser.answers, parser.outcomes)


def load_package_questions(path: Path) -> dict[tuple[str, int], QuestionContext]:
    """Строит индекс (тема, номинал) → раунд из SIQ-пакета."""

    with zipfile.ZipFile(path) as package:
        root = ET.fromstring(package.read("content.xml"))

    def local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    index: dict[tuple[str, int], QuestionContext] = {}
    for round_node in (node for node in root.iter() if local_name(node.tag) == "round"):
        round_name = round_node.get("name", "")
        for theme_node in (node for node in round_node.iter() if local_name(node.tag) == "theme"):
            theme_name = theme_node.get("name", "")
            for question_node in (node for node in theme_node.iter() if local_name(node.tag) == "question"):
                try:
                    price = int(question_node.get("price", "0"))
                except ValueError:
                    continue
                index[(theme_name, price)] = QuestionContext(round_name, theme_name, price)
    return index


STAT_LINE_RE = re.compile(
    r"^(?P<name>.+?):\s*Right:\s*(?P<right>\d+)\s*/\s*(?P<right_total>-?\d+)\s*,\s*"
    r"Wrong:\s*(?P<wrong>\d+)\s*/\s*(?P<wrong_total>-?\d+)\s*$",
    re.IGNORECASE,
)

MANUAL_SCORE_PATTERNS = (
    re.compile(
        r"^.+?\s+изменил(?:\(а\)|а)?\s+сумму\s+на\s+сч[её]те\s+"
        r"(?P<player>.+?)\s+с\s+(?P<old>-?\d+)\s+на\s+(?P<new>-?\d+)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^.+?\s+changed\s+(?P<player>.+?)\s+score\s+from\s+"
        r"(?P<old>-?\d+)\s+to\s+(?P<new>-?\d+)\s*$",
        re.IGNORECASE,
    ),
)


def parse_text_log(
    path: Path,
    content: str,
    question_index: dict[tuple[str, int], QuestionContext] | None = None,
) -> GameData:
    """Читает скачанный TXT-журнал SIOnline.

    SIOnline пишет GAME_STATISTICS в стабильном формате с английскими метками
    Right/Wrong даже при русской локализации интерфейса.
    """

    lines = [line.strip() for line in content.splitlines()]
    stat_rows: dict[str, tuple[int, int, int, int]] = {}
    for line in lines:
        match = STAT_LINE_RE.match(line)
        if match:
            stat_rows[match.group("name")] = (
                int(match.group("right")),
                abs(int(match.group("right_total"))),
                int(match.group("wrong")),
                abs(int(match.group("wrong_total"))),
            )

    if not stat_rows:
        raise ValueError("В TXT-журнале не найден блок GAME_STATISTICS (строки Right/Wrong).")

    players = {name: PlayerMetrics(name=name) for name in stat_rows}
    raw_outcomes: list[Outcome] = []
    sequence = 0

    # WINNER пишет финальный блок «Имя: итог». Отрицательный итог синтаксически
    # совпадает со списанием, поэтому заранее исключаем последнее такое вхождение.
    final_results: dict[str, int] = {}
    final_result_line_indexes: set[int] = set()
    for name in players:
        result_re = re.compile(rf"^{re.escape(name)}:\s*(-?\d+)\s*$")
        matches = [
            (line_index, int(match.group(1)))
            for line_index, line in enumerate(lines)
            if (match := result_re.match(line))
        ]
        if matches:
            line_index, value = matches[-1]
            final_result_line_indexes.add(line_index)
            final_results[name] = value

    # SIOnline пишет начисления отдельными строками «Имя: +100» / «Имя: -100».
    outcome_patterns = {
        name: re.compile(
            rf"^{re.escape(name[1:] if name.startswith('Ⓢ') else name)}:\s*([+-])(\d+)\s*$"
        )
        for name in players
    }
    player_aliases: dict[str, str] = {}
    for name in players:
        player_aliases[name.casefold()] = name
        if name.startswith("Ⓢ"):
            player_aliases[name[1:].casefold()] = name

    current_question: QuestionContext | None = None
    tracked_question_outcomes = 0
    for line_index, line in enumerate(lines):
        if line_index in final_result_line_indexes:
            continue

        if question_index:
            theme_name, separator, price_text = line.rpartition(", ")
            if separator:
                try:
                    price = int(price_text)
                except ValueError:
                    pass
                else:
                    context = question_index.get((theme_name, price))
                    if context:
                        current_question = context

        manual_match = next(
            (match for pattern in MANUAL_SCORE_PATTERNS if (match := pattern.match(line))),
            None,
        )
        if manual_match:
            player_name = player_aliases.get(manual_match.group("player").strip().casefold())
            if player_name:
                sequence += 1
                raw_outcomes.append(
                    Outcome(
                        sequence,
                        player_name,
                        int(manual_match.group("new")) - int(manual_match.group("old")),
                        kind="manual",
                        round_name=current_question.round_name if current_question else None,
                        theme=current_question.theme if current_question else None,
                        question_price=current_question.price if current_question else None,
                    )
                )
                if current_question:
                    tracked_question_outcomes += 1
                continue

        for name, pattern in outcome_patterns.items():
            match = pattern.match(line)
            if not match:
                continue
            sequence += 1
            value = int(match.group(2))
            delta = value if match.group(1) == "+" else -value
            raw_outcomes.append(
                Outcome(
                    sequence,
                    name,
                    delta,
                    round_name=current_question.round_name if current_question else None,
                    theme=current_question.theme if current_question else None,
                    question_price=current_question.price if current_question else None,
                )
            )
            if current_question:
                tracked_question_outcomes += 1
            break

    _calculate_metrics(players, raw_outcomes)

    # Агрегаты от игрового сервера авторитетнее реконструкции строк журнала.
    for name, (right, right_total, wrong, wrong_total) in stat_rows.items():
        player = players[name]
        player.right_count = right
        player.right_total = right_total
        player.wrong_count = wrong
        player.wrong_total = wrong_total
        if not raw_outcomes:
            player.final_score = right_total - wrong_total
            player.min_score = min(0, player.final_score)
            player.max_score = max(0, player.final_score)

    for name, final_score in final_results.items():
        players[name].final_score = final_score

    warnings: list[str] = []
    if not raw_outcomes:
        warnings.append("Нет строк начислений: ачивки на серии и траекторию счёта недоступны.")
    if question_index is None:
        warnings.append("SIQ-пакет не найден: ачивки по темам, раундам и номиналам пропущены.")
    elif raw_outcomes and tracked_question_outcomes == 0:
        warnings.append("В журнале не распознаны выбранные вопросы; вопросные ачивки пропущены.")
    elif tracked_question_outcomes < len(raw_outcomes):
        warnings.append(
            f"К вопросу привязано {tracked_question_outcomes} из {len(raw_outcomes)} изменений счёта."
        )

    round_names = list(dict.fromkeys(
        context.round_name for context in (question_index or {}).values()
    ))
    return GameData(
        source=str(path),
        players=players,
        outcomes=raw_outcomes,
        round_names=round_names,
        warnings=warnings,
    )


def load_game(path: Path, package_path: Path | None = None) -> GameData:
    content = path.read_text(encoding="utf-8-sig", errors="replace")
    if path.suffix.lower() in {".html", ".htm"} or "data-tag=\"gameInfo\"" in content:
        return parse_html_log(path, content)

    question_index = load_package_questions(package_path) if package_path else None
    return parse_text_log(path, content, question_index)


def _leaders(
    players: Iterable[PlayerMetrics],
    value,
    *,
    eligible=lambda player: True,
    reverse: bool = True,
) -> list[PlayerMetrics]:
    candidates = [player for player in players if eligible(player)]
    if not candidates:
        return []
    values = [value(player) for player in candidates]
    best = max(values) if reverse else min(values)
    return [player for player in candidates if value(player) == best]


def _game_round_names(game: GameData) -> list[str]:
    if game.round_names:
        return game.round_names
    return list(dict.fromkeys(
        outcome.round_name for outcome in game.outcomes if outcome.round_name
    ))


def calculate_awards(game: GameData) -> dict[str, list[Award]]:
    players = list(game.players.values())
    awards: dict[str, list[Award]] = {player.name: [] for player in players}

    def give(recipients: Iterable[PlayerMetrics], code: str, title: str, points: int, evidence) -> None:
        for player in recipients:
            text = evidence(player) if callable(evidence) else evidence
            awards[player.name].append(Award(code, title, points, text))

    give(
        _leaders(players, lambda p: p.final_score),
        "champion",
        "Чемпион",
        4,
        lambda p: f"лучший итоговый счёт: {p.final_score}",
    )
    give(
        _leaders(players, lambda p: p.right_count, eligible=lambda p: p.right_count > 0),
        "erudite",
        "Главный мозг",
        3,
        lambda p: f"больше всего верных ответов: {p.right_count}",
    )
    give(
        _leaders(
            players,
            lambda p: round(p.accuracy or 0.0, 12),
            eligible=lambda p: p.attempts >= MIN_ACCURACY_ATTEMPTS,
        ),
        "sniper",
        "Снайпер",
        2,
        lambda p: f"лучшая точность при ≥{MIN_ACCURACY_ATTEMPTS} попытках: {p.accuracy:.1%}",
    )
    give(
        _leaders(
            players,
            lambda p: len(p.positive_by_theme),
            eligible=lambda p: bool(p.positive_by_theme),
        ),
        "polymath",
        "Широкий кругозор",
        2,
        lambda p: (
            "положительный результат в 1 теме"
            if len(p.positive_by_theme) == 1
            else f"положительный результат в {len(p.positive_by_theme)} разных темах"
        ),
    )
    give(
        _leaders(
            players,
            lambda p: sum(count for price, count in p.right_by_price.items() if price >= 900),
            eligible=lambda p: any(price >= 900 for price in p.right_by_price),
        ),
        "big_game_hunter",
        "Охотник на крупняк",
        2,
        lambda p: (
            "верных ответов на вопросы от 900: "
            f"{sum(count for price, count in p.right_by_price.items() if price >= 900)}"
        ),
    )
    give(
        [p for p in players if p.min_score <= COMEBACK_FLOOR and p.final_score > 0],
        "comeback",
        "Камбэк",
        2,
        lambda p: f"поднялся с {p.min_score} до {p.final_score}",
    )

    # По одному небольшому призу за лидерство в каждом раунде. Полный список
    # берём из SIQ-пакета, а без него восстанавливаем из журнала.
    round_names = _game_round_names(game)
    for round_index, round_name in enumerate(round_names, start=1):
        give(
            _leaders(
                players,
                lambda p, name=round_name: p.net_by_round.get(name, 0),
                eligible=lambda p, name=round_name: p.net_by_round.get(name, 0) > 0,
            ),
            f"round_king_{round_index}",
            f"Король раунда «{round_name}»",
            1,
            lambda p, name=round_name: f"результат раунда: {p.net_by_round.get(name, 0)} очков",
        )

    # Рофельные и утешительные — по одной подсказке.
    give(
        _leaders(players, lambda p: abs(p.final_score - TARGET_SCORE), reverse=False),
        "almost_6767",
        "Почти 6767",
        1,
        lambda p: f"счёт {p.final_score}, расстояние {abs(p.final_score - TARGET_SCORE)}",
    )
    give(
        _leaders(players, lambda p: p.wrong_count, eligible=lambda p: p.wrong_count > 0),
        "professor_minus",
        "Профессор минусов",
        1,
        lambda p: f"больше всего неверных ответов: {p.wrong_count}",
    )
    give(
        _leaders(
            players,
            lambda p: round(abs((p.accuracy or 0.0) - 0.5), 12),
            eligible=lambda p: p.attempts >= MIN_ACCURACY_ATTEMPTS,
            reverse=False,
        ),
        "fifty_fifty",
        "Монетка 50/50",
        1,
        lambda p: f"точность ближе всех к 50%: {p.accuracy:.1%}",
    )
    give(
        [p for p in players if p.right_count >= 5 and p.wrong_count >= 5],
        "rollercoaster",
        "Американские горки",
        1,
        lambda p: f"{p.right_count} верных и {p.wrong_count} неверных",
    )
    give(
        [p for p in players if p.max_wrong_streak >= 3],
        "three_strikes",
        "Три страйка",
        1,
        lambda p: f"серия из {p.max_wrong_streak} ошибок подряд",
    )
    give(
        _leaders(
            players,
            lambda p: max(p.net_by_theme.values(), default=0),
            eligible=lambda p: any(value > 0 for value in p.net_by_theme.values()),
        ),
        "theme_specialist",
        "Тематический маньяк",
        1,
        lambda p: (
            f"лучший результат в одной теме: {max(p.net_by_theme.values())} очков "
            f"({', '.join(name for name, value in p.net_by_theme.items() if value == max(p.net_by_theme.values()))})"
        ),
    )
    give(
        _leaders(
            players,
            lambda p: sum(count for price, count in p.right_by_price.items() if price <= 300),
            eligible=lambda p: any(price <= 300 for price in p.right_by_price),
        ),
        "easy_pickings",
        "Любитель халявы",
        1,
        lambda p: (
            "верных ответов на вопросы до 300: "
            f"{sum(count for price, count in p.right_by_price.items() if price <= 300)}"
        ),
    )
    give(
        [p for p in players if p.returned_to_zero],
        "reset_zero",
        "Заводские настройки",
        1,
        "вернулся ровно к нулю после ненулевого счёта",
    )
    give(
        [p for p in players if max(p.max_gain, p.max_loss) >= HIGH_ROLLER_DELTA],
        "high_roller",
        "На все деньги",
        1,
        lambda p: f"один скачок счёта: {max(p.max_gain, p.max_loss)}",
    )

    last_right = next(
        (outcome for outcome in reversed(game.outcomes) if outcome.kind == "answer" and outcome.delta > 0),
        None,
    )
    if last_right:
        give(
            [game.players[last_right.player]],
            "last_word",
            "Последнее слово",
            1,
            f"последний верный ответ (+{last_right.delta})",
        )

    give(
        [p for p in players if p.final_score < 0],
        "bankrupt",
        "Долговая яма",
        1,
        lambda p: f"финишировал с отрицательным счётом: {p.final_score}",
    )
    give(
        [
            p for p in players
            if len(str(abs(p.final_score))) >= 3
            and str(abs(p.final_score)) == str(abs(p.final_score))[::-1]
        ],
        "palindrome",
        "Красивый номер",
        1,
        lambda p: f"итоговый счёт-палиндром: {p.final_score}",
    )
    give(
        [p for p in players if p.attempts >= MIN_ACCURACY_ATTEMPTS and p.right_count == p.wrong_count],
        "balanced",
        "Идеальный баланс",
        1,
        lambda p: f"поровну верных и неверных: {p.right_count}/{p.wrong_count}",
    )

    return awards


def _default_logs_dirs() -> list[Path]:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return []

    root = Path(local_app_data)
    return [
        # Steam / SIGame 8 (Tauri app_log_dir).
        root / "com.vladimirkhil.sigame" / "logs",
        # Классическая настольная SIGame 7.
        root / "Khil-soft" / "SIGame" / "Logs",
    ]


def find_latest_log(path: Path | None) -> Path:
    bases = [path] if path is not None else _default_logs_dirs()
    if not bases:
        raise FileNotFoundError("Не задан журнал и не найдена переменная LOCALAPPDATA.")

    candidates: list[Path] = []
    for base in bases:
        if base.is_file():
            candidates.append(base)
        elif base.exists():
            candidates.extend(
                item for item in base.rglob("*")
                if item.is_file()
                and item.suffix.lower() in {".html", ".htm", ".txt"}
                and not item.name.endswith("-achievements.txt")
            )

    if not candidates:
        checked = ", ".join(str(base) for base in bases)
        raise FileNotFoundError(f"Журналы HTML/TXT не найдены. Проверено: {checked}")
    return max(candidates, key=lambda item: item.stat().st_mtime)


REPORT_ORDER = {
    "champion": 10,
    "erudite": 20,
    "sniper": 30,
    "polymath": 40,
    "big_game_hunter": 50,
    "comeback": 60,
    "almost_6767": 200,
    "professor_minus": 210,
    "fifty_fifty": 220,
    "rollercoaster": 230,
    "three_strikes": 240,
    "theme_specialist": 250,
    "easy_pickings": 260,
    "reset_zero": 270,
    "high_roller": 280,
    "last_word": 290,
    "bankrupt": 300,
    "palindrome": 310,
    "balanced": 320,
}

# Полный каталог нужен отчёту: ачивка отображается, даже если её никто не получил.
STATIC_AWARD_CATALOG = (
    ("champion", "Чемпион", 4),
    ("erudite", "Главный мозг", 3),
    ("sniper", "Снайпер", 2),
    ("polymath", "Широкий кругозор", 2),
    ("big_game_hunter", "Охотник на крупняк", 2),
    ("comeback", "Камбэк", 2),
    ("almost_6767", "Почти 6767", 1),
    ("professor_minus", "Профессор минусов", 1),
    ("fifty_fifty", "Монетка 50/50", 1),
    ("rollercoaster", "Американские горки", 1),
    ("three_strikes", "Три страйка", 1),
    ("theme_specialist", "Тематический маньяк", 1),
    ("easy_pickings", "Любитель халявы", 1),
    ("reset_zero", "Заводские настройки", 1),
    ("high_roller", "На все деньги", 1),
    ("last_word", "Последнее слово", 1),
    ("bankrupt", "Долговая яма", 1),
    ("palindrome", "Красивый номер", 1),
    ("balanced", "Идеальный баланс", 1),
)


def _hint_word(value: int) -> str:
    if value % 10 == 1 and value % 100 != 11:
        return "подсказка"
    if value % 10 in (2, 3, 4) and value % 100 not in (12, 13, 14):
        return "подсказки"
    return "подсказок"


def render_report(game: GameData, awards: dict[str, list[Award]]) -> str:
    grouped: dict[tuple[str, str, int], list[tuple[str, str]]] = {
        definition: [] for definition in STATIC_AWARD_CATALOG
    }

    # Раундовые ачивки динамические: выводим отдельную для каждого раунда пакета,
    # даже если в журнале нет победителя или изменений счёта этого раунда.
    round_names = _game_round_names(game)
    for round_index, round_name in enumerate(round_names, start=1):
        grouped[(
            f"round_king_{round_index}",
            f"Король раунда «{round_name}»",
            1,
        )] = []

    for player_name, player_awards in awards.items():
        for award in player_awards:
            key = (award.code, award.title, award.points)
            grouped.setdefault(key, []).append((player_name, award.evidence))

    def award_order(item: tuple[tuple[str, str, int], list[tuple[str, str]]]) -> tuple[int, str]:
        code, title, _ = item[0]
        if code.startswith("round_king_"):
            return (100 + int(code.rsplit("_", 1)[1]), title)
        return (REPORT_ORDER.get(code, 999), title)

    lines = [
        "АЧИВКИ SIGAME",
        f"Источник: {Path(game.source).name}",
        "",
    ]

    for number, ((_, title, points), recipients) in enumerate(
        sorted(grouped.items(), key=award_order),
        start=1,
    ):
        lines.append(f"{number}. {title} — {points} {_hint_word(points)}")
        if recipients:
            for player_name, evidence in recipients:
                lines.append(f"   {player_name} — {evidence}")
        else:
            lines.append("   Никто не получил")
        lines.append("")

    lines.append("ИТОГО К НАЧИСЛЕНИЮ")
    for player_name, player_awards in awards.items():
        total = sum(award.points for award in player_awards)
        lines.append(f"{player_name} — {total} {_hint_word(total)}")

    if game.warnings:
        lines.extend(["", "ПРЕДУПРЕЖДЕНИЯ"])
        lines.extend(f"- {warning}" for warning in game.warnings)

    return "\n".join(lines).rstrip() + "\n"


def report_path_for(log_path: Path) -> Path:
    return REPORTS_DIR / f"{log_path.stem}-achievements.txt"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Создаёт TXT-отчёт с ачивками по журналу SIGame/Steam."
    )
    parser.add_argument(
        "log",
        nargs="?",
        type=Path,
        help="журнал или папка; без аргумента берётся последний журнал Steam",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        path = find_latest_log(args.log)
        package_candidates = [
            Path.cwd() / "zengame.siq",
            REPO_ROOT / "zengame.siq",
        ]
        package_path = next((item for item in package_candidates if item.exists()), None)

        game = load_game(path, package_path)
        if not game.players:
            raise ValueError("В журнале не найдены игроки.")

        awards = calculate_awards(game)
        output_path = report_path_for(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_report(game, awards), encoding="utf-8")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
