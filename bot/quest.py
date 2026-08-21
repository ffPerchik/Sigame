"""Загрузка квеста: пролог, гейт перед хабом, шесть независимых узлов."""
import re
from collections import OrderedDict
from typing import Optional

import yaml

try:
    from .config import QUEST_FILE
except ImportError:  # прямой запуск файлов из папки bot
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
    """Первая стадия пролога сразу после /start <код>."""
    return "z_1"


# ---- Приветствие ----
def welcome_info() -> dict:
    """Возвращает {text, image?} из секции welcome."""
    q = load()
    return q.get("welcome", {})


# ---- Метаданные узлов для хаба ----
def nodes_meta() -> OrderedDict:
    """Возвращает OrderedDict {node_id: {label, hint}} из секции nodes,
    сохраняя порядок N1…N6. """
    q = load()
    raw = q.get("nodes", {})
    # сортируем по ключу (N1…N6)
    ordered = OrderedDict()
    for nid in ("N1", "N2", "N3", "N4", "N5", "N6"):
        if nid in raw:
            ordered[nid] = raw[nid]
    return ordered


def get_stage(stage_id: str) -> Optional[dict]:
    return load().get("stages", {}).get(stage_id)


def is_gate(stage_id: str) -> bool:
    st = get_stage(stage_id)
    return bool(st and st.get("mode") == "gate")


def is_finish(stage_id: str) -> bool:
    st = get_stage(stage_id)
    return bool(st and st.get("mode") == "finish")


def is_info(stage_id: str) -> bool:
    st = get_stage(stage_id)
    return bool(st and st.get("mode") == "info")


def is_hub(stage_id: str) -> bool:
    """Хаб — это виртуальная стадия, обрабатывается кодом."""
    return stage_id == "hub"


def extract_node_id(stage_id: str) -> Optional[str]:
    """По stage_id (например «N1_place») возвращает node_id (например «N1»)."""
    for prefix in ("N1", "N2", "N3", "N4", "N5", "N6"):
        if stage_id.startswith(prefix + "_"):
            return prefix
    return None


# ---- Валидация ответов ----
def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = s.replace("ё", "е")
    s = re.sub(r"[^a-zа-я0-9]+", " ", s)
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