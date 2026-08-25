"""Загрузка квеста с безопасным автоматическим обновлением stages.yaml."""
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import yaml

try:
    from .config import QUEST_FILE
except ImportError:  # прямой запуск файлов из папки bot
    from config import QUEST_FILE

_QUEST: Optional[dict] = None
_QUEST_MTIME_NS: Optional[int] = None
_FAILED_MTIME_NS: Optional[int] = None
_NEXT_AUTO_CHECK = 0.0
_AUTO_RELOAD_INTERVAL = 1.0


def _read_from_disk() -> tuple[dict, int]:
    path = Path(QUEST_FILE)
    mtime_ns = path.stat().st_mtime_ns
    with path.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict) or not isinstance(data.get("stages"), dict):
        raise ValueError(f"В {path} нет mapping-секции 'stages'")
    return data, mtime_ns


def reload_from_disk() -> tuple[bool, str]:
    """Принудительно перечитывает сценарий, не ломая старый при ошибке."""
    global _QUEST, _QUEST_MTIME_NS, _FAILED_MTIME_NS, _NEXT_AUTO_CHECK
    try:
        data, mtime_ns = _read_from_disk()
    except Exception as error:
        try:
            _FAILED_MTIME_NS = Path(QUEST_FILE).stat().st_mtime_ns
        except OSError:
            _FAILED_MTIME_NS = None
        return False, f"{type(error).__name__}: {error}"

    _QUEST = data
    _QUEST_MTIME_NS = mtime_ns
    _FAILED_MTIME_NS = None
    _NEXT_AUTO_CHECK = time.monotonic() + _AUTO_RELOAD_INTERVAL
    return True, f"стадий: {len(data['stages'])}"


def load() -> dict:
    """Возвращает актуальный сценарий; mtime проверяется не чаще раза в секунду."""
    global _NEXT_AUTO_CHECK
    if _QUEST is None:
        ok, details = reload_from_disk()
        if not ok:
            raise RuntimeError(f"Не удалось загрузить сценарий: {details}")
        return _QUEST

    now = time.monotonic()
    if now >= _NEXT_AUTO_CHECK:
        _NEXT_AUTO_CHECK = now + _AUTO_RELOAD_INTERVAL
        try:
            mtime_ns = Path(QUEST_FILE).stat().st_mtime_ns
        except OSError as error:
            print(f"[QUEST] автообновление пропущено: {error}", flush=True)
        else:
            if mtime_ns != _QUEST_MTIME_NS and mtime_ns != _FAILED_MTIME_NS:
                ok, details = reload_from_disk()
                if ok:
                    print(f"[QUEST] сценарий автоматически обновлён ({details})", flush=True)
                else:
                    print(
                        f"[QUEST] ошибка обновления, оставлена предыдущая версия: {details}",
                        flush=True,
                    )
    return _QUEST


def entry_code() -> str:
    return str(load().get("entry_code", "")).strip()


def first_stage() -> str:
    """Первая стадия пролога сразу после обычного /start."""
    return "z_1"


# ---- Приветствие ----
def welcome_info() -> dict:
    """Возвращает {text, image?, speaker?, delay?} из секции welcome."""
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