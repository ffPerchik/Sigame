"""Проверка файлов и самоперезапуск процесса бота для команды /update."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import NoReturn, Sequence


def validate_python_tree(root: Path) -> tuple[bool, str]:
    """Проверяет синтаксис всех Python-файлов, ничего из них не выполняя."""
    files = sorted(root.rglob("*.py"))
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
        except (OSError, SyntaxError, UnicodeError) as error:
            try:
                name = path.relative_to(root)
            except ValueError:
                name = path
            return False, f"{name}: {type(error).__name__}: {error}"
    return True, f"Python-файлов: {len(files)}"


def restart_current_process(
    argv: Sequence[str] | None = None,
    executable: str | None = None,
) -> NoReturn:
    """Заменяет текущий процесс свежим Python-процессом с теми же аргументами."""
    executable = executable or sys.executable
    args = list(sys.argv if argv is None else argv)
    os.execv(executable, [executable, *args])
    raise RuntimeError("os.execv unexpectedly returned")
