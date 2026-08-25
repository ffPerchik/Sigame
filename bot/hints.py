"""Нормализация одной или нескольких подсказок стадии."""
from __future__ import annotations


def stage_hints(stage: dict | None) -> list[str]:
    """Возвращает подсказки по порядку; `hints` имеет приоритет над старым `hint`."""
    if not stage:
        return []
    raw = stage.get("hints") if "hints" in stage else stage.get("hint")
    if isinstance(raw, str):
        value = raw.strip()
        return [value] if value else []
    if isinstance(raw, (list, tuple)):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []
