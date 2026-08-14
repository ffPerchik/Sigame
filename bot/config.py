"""Конфиг бота. Все параметры — в .env (см. .env.example)."""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent


def _load_env() -> None:
    env = BASE / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
HOST_ID = int(os.environ.get("HOST_ID", "0"))
ENTRY_CODE = os.environ.get("ENTRY_CODE", "ZENGAME2026")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "").lstrip("@")
DB_PATH = os.environ.get("DB_PATH") or str(BASE / "quest.db")
QUEST_FILE = os.environ.get("QUEST_FILE") or str(BASE / "quest" / "stages.yaml")
NOTIFY_HOST = os.environ.get("NOTIFY_HOST", "1") == "1"

if not BOT_TOKEN or not HOST_ID:
    raise RuntimeError("Заполни BOT_TOKEN и HOST_ID в bot/.env (см. .env.example)")
