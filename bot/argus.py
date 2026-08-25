"""Форматирование реплик ARGVS-1001 с реальным локальным временем."""
from __future__ import annotations

from datetime import datetime


def timestamp(now: datetime | None = None) -> str:
    """Локальное реальное время с миллисекундами."""
    moment = now or datetime.now().astimezone()
    return f"{moment:%H:%M:%S}.{moment.microsecond // 1000:03d}"


def format_line(text: str, now: datetime | None = None) -> str:
    return f"[{timestamp(now)}] ARGVS-1001 // {text.strip()}"
