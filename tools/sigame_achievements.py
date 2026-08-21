#!/usr/bin/env python3
"""Подсчёт ачивок и подсказок по журналу SIGame.

Поддерживаются:
* HTML-журнал настольной SIGame (предпочтительно: содержит тексты ответов);
* TXT-журнал SIOnline (агрегаты GAME_STATISTICS, без текстов ответов).

Зависимостей вне стандартной библиотеки Python нет.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


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


@dataclass
class Outcome:
    sequence: int
    player: str
    delta: int
    answer: str | None = None


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
    answer_67_count: int = 0
    answers: list[str] = field(default_factory=list)

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

        if player.final_score != 0:
            was_nonzero[outcome.player] = True
        elif was_nonzero[outcome.player]:
            player.returned_to_zero = True

        if outcome.delta > 0:
            player.right_count += 1
            player.right_total += outcome.delta
            player.max_gain = max(player.max_gain, outcome.delta)
            current_right_streak[outcome.player] += 1
            current_wrong_streak[outcome.player] = 0
        elif outcome.delta < 0:
            loss = abs(outcome.delta)
            player.wrong_count += 1
            player.wrong_total += loss
            player.max_loss = max(player.max_loss, loss)
            current_wrong_streak[outcome.player] += 1
            current_right_streak[outcome.player] = 0

        player.max_right_streak = max(player.max_right_streak, current_right_streak[outcome.player])
        player.max_wrong_streak = max(player.max_wrong_streak, current_wrong_streak[outcome.player])

    token_67 = re.compile(r"(?<!\d)67(?!\d)")
    for player in players.values():
        player.answer_67_count = sum(len(token_67.findall(answer)) for answer in player.answers)


def parse_html_log(path: Path, content: str) -> GameData:
    parser = SIGameHTMLParser()
    parser.feed(content)
    parser.close()
    return _build_game_from_raw(str(path), parser.player_names, parser.answers, parser.outcomes)


STAT_LINE_RE = re.compile(
    r"^(?P<name>.+?):\s*Right:\s*(?P<right>\d+)\s*/\s*(?P<right_total>-?\d+)\s*,\s*"
    r"Wrong:\s*(?P<wrong>\d+)\s*/\s*(?P<wrong_total>-?\d+)\s*$",
    re.IGNORECASE,
)


def parse_text_log(path: Path, content: str) -> GameData:
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

    # SIOnline пишет начисления отдельными строками «Имя: +100» / «Имя: -100».
    outcome_patterns = {
        name: re.compile(rf"^{re.escape(name)}:\s*([+-])(\d+)\s*$")
        for name in players
    }
    for line in lines:
        for name, pattern in outcome_patterns.items():
            match = pattern.match(line)
            if not match:
                continue
            sequence += 1
            value = int(match.group(2))
            raw_outcomes.append(Outcome(sequence, name, value if match.group(1) == "+" else -value))
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

    # Финальные строки «Имя: 1234» идут после результатов. Берём последнее
    # вхождение для каждого уже известного игрока.
    for name, player in players.items():
        result_re = re.compile(rf"^{re.escape(name)}:\s*(-?\d+)\s*$")
        results = [int(match.group(1)) for line in lines if (match := result_re.match(line))]
        if results:
            player.final_score = results[-1]

    warnings = [
        "TXT-журнал SIOnline не содержит тексты PLAYER_ANSWER: ачивки «67» и «Лонгрид» недоступны."
    ]
    if not raw_outcomes:
        warnings.append("Нет строк начислений: ачивки на серии и траекторию счёта недоступны.")

    return GameData(source=str(path), players=players, outcomes=raw_outcomes, warnings=warnings)


def load_game(path: Path) -> GameData:
    content = path.read_text(encoding="utf-8-sig", errors="replace")
    if path.suffix.lower() in {".html", ".htm"} or "data-tag=\"gameInfo\"" in content:
        return parse_html_log(path, content)
    return parse_text_log(path, content)


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
        _leaders(players, lambda p: p.right_total, eligible=lambda p: p.right_total > 0),
        "banker",
        "Банкир",
        2,
        lambda p: f"больше всего набрано верными ответами: {p.right_total}",
    )
    give(
        [p for p in players if p.min_score <= COMEBACK_FLOOR and p.final_score > 0],
        "comeback",
        "Камбэк",
        2,
        lambda p: f"поднялся с {p.min_score} до {p.final_score}",
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
        _leaders(players, lambda p: p.answer_67_count, eligible=lambda p: p.answer_67_count > 0),
        "area_67",
        "67-й регион",
        1,
        lambda p: f"ответов с отдельным числом 67: {p.answer_67_count}",
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

    last_right = next((outcome for outcome in reversed(game.outcomes) if outcome.delta > 0), None)
    if last_right:
        give(
            [game.players[last_right.player]],
            "last_word",
            "Последнее слово",
            1,
            f"последний верный ответ (+{last_right.delta})",
        )

    wrong_with_text = [
        outcome for outcome in game.outcomes
        if outcome.delta < 0 and outcome.answer and outcome.answer.strip()
    ]
    if wrong_with_text:
        longest = max(len(outcome.answer.strip()) for outcome in wrong_with_text if outcome.answer)
        names = {
            outcome.player
            for outcome in wrong_with_text
            if outcome.answer and len(outcome.answer.strip()) == longest
        }
        give(
            [game.players[name] for name in names],
            "longread",
            "Лонгрид не помог",
            1,
            f"самый длинный неверный ответ: {longest} символов",
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
                if item.is_file() and item.suffix.lower() in {".html", ".htm", ".txt"}
            )

    if not candidates:
        checked = ", ".join(str(base) for base in bases)
        raise FileNotFoundError(f"Журналы HTML/TXT не найдены. Проверено: {checked}")
    return max(candidates, key=lambda item: item.stat().st_mtime)


def load_mapping(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Файл соответствий должен быть JSON-объектом {\"Имя SIGame\": \"@telegram\"}.")
    return {str(key): str(value) for key, value in raw.items()}


def render_report(game: GameData, awards: dict[str, list[Award]], mapping: dict[str, str]) -> str:
    lines = [f"Источник: {game.source}", "", "Статистика:"]
    for player in game.players.values():
        accuracy = f"{player.accuracy:.1%}" if player.accuracy is not None else "—"
        lines.append(
            f"  {player.name}: счёт {player.final_score}; ✓ {player.right_count}; "
            f"✗ {player.wrong_count}; точность {accuracy}"
        )

    lines.extend(["", "Ачивки и подсказки:"])
    for name, player_awards in awards.items():
        total = sum(award.points for award in player_awards)
        lines.append(f"  {name} — {total}")
        for award in player_awards:
            lines.append(f"    +{award.points} {award.title} — {award.evidence}")

    if game.warnings:
        lines.extend(["", "Предупреждения:"])
        lines.extend(f"  ! {warning}" for warning in game.warnings)

    lines.extend(["", "Команды для Telegram-бота:"])
    for name, player_awards in awards.items():
        total = sum(award.points for award in player_awards)
        target = mapping.get(name)
        if total <= 0:
            continue
        if target:
            if not target.startswith("@") and not target.isdigit():
                target = "@" + target
            lines.append(f"  /addhint {target} {total}")
        else:
            lines.append(f"  # {name}: +{total} (добавь соответствие SIGame → Telegram)")

    return "\n".join(lines)


def json_report(game: GameData, awards: dict[str, list[Award]], mapping: dict[str, str]) -> dict:
    return {
        "source": game.source,
        "warnings": game.warnings,
        "players": {
            name: {
                "metrics": asdict(player),
                "awards": [asdict(award) for award in awards[name]],
                "hint_total": sum(award.points for award in awards[name]),
                "telegram": mapping.get(name),
            }
            for name, player in game.players.items()
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Считает ачивки и подсказки по журналу SIGame/SIOnline."
    )
    parser.add_argument(
        "log",
        nargs="?",
        type=Path,
        help="HTML/TXT-журнал или папка с журналами; без аргумента ищется последний лог SIGame",
    )
    parser.add_argument(
        "--map",
        dest="mapping",
        type=Path,
        help="JSON соответствий имён SIGame Telegram username/id",
    )
    parser.add_argument("--json-out", type=Path, help="дополнительно сохранить полный отчёт в JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        path = find_latest_log(args.log)
        game = load_game(path)
        if not game.players:
            raise ValueError("В журнале не найдены игроки.")
        mapping = load_mapping(args.mapping)
        awards = calculate_awards(game)
        report = render_report(game, awards, mapping)
        print(report)
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(
                json.dumps(json_report(game, awards, mapping), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
