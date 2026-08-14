"""Загрузка и проверка квеста (quest/stages.yaml)."""
import re
from pathlib import Path
from typing import Optional

import yaml

from config import QUEST_FILE

_QUEST: Optional[dict] = None


def load() -> dict:
    global _QUEST
    if _QUEST is None:
        with open(QUEST_FILE, encoding="utf-8") as f:
            _QUEST = yaml.safe_load(f)
        if "stages" not in _QUEST:
            raise ValueError(f"В {QUEST_FILE} нет секции 'stages'")
    return _QUEST


def entry_code() -> str:
    return str(load().get("entry_code", "")).strip()


def first_stage() -> str:
    q = load()
    if q.get("start"):
        return q["start"]
    return next(iter(q["stages"]))


def get_stage(stage_id: str) -> Optional[dict]:
    return load().get("stages", {}).get(stage_id)


def is_finish(stage_id: str) -> bool:
    st = get_stage(stage_id)
    return bool(st and st.get("mode") == "finish")


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = s.replace("ё", "е")
    s = re.sub(r"[^a-zа-я0-9]+", " ", s)  # пунктуацию/лишние пробелы — в один пробел
    return re.sub(r"\s+", " ", s).strip()


def validate(accept, answer: str) -> bool:
    """Нормализованное сравнение (без регистра/ё/лишней пунктуации)."""
    if not accept:
        return False
    if isinstance(accept, str):
        accept = [accept]
    a = _norm(answer)
    return a in {_norm(x) for x in accept}


def qr_stages() -> dict:
    """stage_id -> код для QR (первый accept), только qr-стадии."""
    out = {}
    for sid, st in load().get("stages", {}).items():
        if st.get("qr") and st.get("accept"):
            codes = st["accept"] if isinstance(st["accept"], list) else [st["accept"]]
            out[sid] = codes[0]
    return out
