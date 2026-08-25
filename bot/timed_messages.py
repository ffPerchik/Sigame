"""Последовательности сообщений с задержкой перед каждым сообщением."""
from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncContextManager

try:
    from .argus import format_line as format_argus_line
except ImportError:  # прямой запуск файлов из папки bot
    from argus import format_line as format_argus_line


@dataclass(frozen=True)
class TimedMessage:
    text: str
    delay: float = 0.0
    speaker: str = ""


def normalize_messages(items: Iterable[object]) -> list[TimedMessage]:
    """Преобразует YAML-элементы в сообщения.

    Формат элемента:
      {text: "...", delay: 0.5, speaker: argus}

    `delay` всегда означает паузу ПЕРЕД этим элементом. Многострочная реплика
    Аргуса разбивается на отдельные сообщения с той же задержкой перед каждым.
    """
    result: list[TimedMessage] = []
    for item in items:
        if isinstance(item, str):
            text, delay, speaker = item, 0.0, ""
        elif isinstance(item, dict):
            text = str(item.get("text", ""))
            delay = max(0.0, float(item.get("delay", 0.0)))
            speaker = str(item.get("speaker", "")).strip().lower()
        else:
            raise TypeError(f"Сообщение должно быть строкой или mapping, получено: {type(item).__name__}")

        if speaker == "argus":
            lines = [line.strip() for line in text.splitlines() if line.strip()]
        else:
            lines = [text.strip()] if text.strip() else []
        result.extend(TimedMessage(line, delay, speaker) for line in lines)
    return result


async def send_typewriter(
    text: str,
    send: Callable[[str], Awaitable[object]],
    edit: Callable[[object, str], Awaitable[object]],
    *,
    interval: float = 0.15,
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
) -> object | None:
    """Отправляет первое слово и затем добавляет по одному слову за правку."""
    text = text.strip()
    if not text:
        return None

    interval = max(0.0, float(interval))
    # Конец версии всегда совпадает с концом слова. Поэтому Telegram не обрежет
    # хвостовой пробел и не ответит ошибкой «message is not modified».
    versions = [text[:match.end()] for match in re.finditer(r"\S+", text)]

    message = await send(versions[0])
    for partial in versions[1:]:
        if interval:
            await sleep(interval)
        await edit(message, partial)
    return message


async def send_messages(
    items: Iterable[object],
    send: Callable[[str], Awaitable[object]],
    *,
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    now_factory: Callable[[], datetime] | None = None,
    activity: Callable[[TimedMessage], AsyncContextManager[object] | None] | None = None,
    progressive_send: Callable[[str], Awaitable[object]] | None = None,
) -> None:
    """Ждёт delay каждого элемента, затем отправляет именно этот элемент.

    `activity` позволяет держать Telegram chat action (например, typing) активным
    во время ожидания и до фактической отправки сообщения. `progressive_send`
    используется для поэтапной отправки реплик Жени.
    """

    async def deliver(item: TimedMessage) -> None:
        if item.delay:
            await sleep(item.delay)
        if item.speaker == "argus":
            now = now_factory() if now_factory else None
            text = format_argus_line(item.text, now)
        else:
            text = item.text
        if item.speaker == "zhenya" and progressive_send:
            await progressive_send(text)
        else:
            await send(text)

    for item in normalize_messages(items):
        context = activity(item) if activity else None
        if context is None:
            await deliver(item)
        else:
            async with context:
                await deliver(item)


async def wait_before(
    delay: object,
    *,
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
) -> None:
    """Общая задержка перед обычным текстом/медиа стадии."""
    seconds = max(0.0, float(delay or 0.0))
    if seconds:
        await sleep(seconds)
