"""Разбор ссылок на медиа и флага Telegram-сжатия."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

COMPRESS_FLAGS = ("-c", "-с", "--compress")  # вторая `с` — кириллическая
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


@dataclass(frozen=True)
class MediaSpec:
    path: str
    compress: bool = False


def parse_media_spec(value: object) -> MediaSpec:
    """Читает `имя файла -c`; флаг обязан стоять в конце через пробел."""
    raw = str(value or "").strip()
    for flag in COMPRESS_FLAGS:
        suffix = " " + flag
        if raw.lower().endswith(suffix):
            path = raw[:-len(suffix)].strip()
            if not path:
                raise ValueError("Перед флагом сжатия не указано имя файла")
            return MediaSpec(path=path, compress=True)
    if not raw:
        raise ValueError("Пустое имя медиафайла")
    return MediaSpec(path=raw)


def delivery_field(field: str, spec: MediaSpec) -> str:
    """`document: image.png -c` отправляется как Telegram photo."""
    if not spec.compress:
        return field
    if field != "document":
        return field  # image и так сжимается, остальные типы не меняем
    if Path(spec.path).suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError("Флаг -c у document поддерживается только для картинок")
    return "image"
