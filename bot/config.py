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
_raw_host = os.environ.get("HOST_ID", "0").strip()
# HOST_CONSOLE=1 — письма ведущему в stdout, не в Telegram (соло-тест с одного аккаунта).
# То же самое, если HOST_ID записан как 123456_1.
HOST_CONSOLE = os.environ.get("HOST_CONSOLE", "0").strip() == "1"
if _raw_host.endswith("_1"):
    HOST_CONSOLE = True
    _raw_host = _raw_host[: -2]
HOST_ID = int(_raw_host or "0")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "").lstrip("@")
# Прокси для обхода блокировки api.telegram.org (Россия). Форматы:
#   http://host:port          http://user:pass@host:port
#   socks5://host:port        socks5://user:pass@host:port
# Пусто — прямое подключение.
PROXY = os.environ.get("PROXY", "").strip()
DB_PATH = os.environ.get("DB_PATH") or str(BASE / "quest.db")
QUEST_FILE = os.environ.get("QUEST_FILE") or str(BASE / "quest" / "stages.yaml")
NOTIFY_HOST = os.environ.get("NOTIFY_HOST", "1") == "1"

if not BOT_TOKEN or not HOST_ID:
    raise RuntimeError("Заполни BOT_TOKEN и HOST_ID в bot/.env (см. .env.example)")
