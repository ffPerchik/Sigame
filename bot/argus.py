"""Форматирование и последовательная отправка реплик ARGVS-1001."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime


def timestamp(now: datetime | None = None) -> str:
    """Локальное реальное время с миллисекундами."""
    moment = now or datetime.now().astimezone()
    return f"{moment:%H:%M:%S}.{moment.microsecond // 1000:03d}"


def format_line(text: str, now: datetime | None = None) -> str:
    return f"[{timestamp(now)}] ARGVS-1001 // {text.strip()}"


def normalize_lines(lines: Iterable[object]) -> list[str]:
    """Даже многострочный YAML-элемент превращает в отдельные сообщения."""
    result = []
    for value in lines:
        result.extend(line.strip() for line in str(value).splitlines() if line.strip())
    return result


async def send_lines(
    lines: Iterable[object],
    send: Callable[[str], Awaitable[object]],
    delay: float = 0.5,
    *,
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    now_factory: Callable[[], datetime] | None = None,
) -> None:
    """Отправляет каждую реплику отдельным сообщением с паузой между ними."""
    normalized = normalize_lines(lines)
    pause = max(0.0, float(delay))
    for index, line in enumerate(normalized):
        if index:
            await sleep(pause)
        now = now_factory() if now_factory else None
        await send(format_line(line, now))
