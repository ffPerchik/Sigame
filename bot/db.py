"""Хранилище прогресса: SQLite (игроки, сабмиты на апрув, подсказки, лог)."""
import sqlite3
import time
from typing import Optional

from config import DB_PATH


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def init_db() -> None:
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS players (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                name        TEXT,
                stage       TEXT,
                started_at  REAL,
                finished_at REAL,
                score       INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS submissions (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER,
                stage    TEXT,
                kind     TEXT,
                payload  TEXT,
                file_id  TEXT,
                status   TEXT DEFAULT 'pending',
                ts       REAL
            );
            CREATE TABLE IF NOT EXISTS hints (
                user_id INTEGER, stage TEXT, used INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, stage)
            );
            CREATE TABLE IF NOT EXISTS log (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, event TEXT, detail TEXT, ts REAL
            );
            """
        )
        # миграции (для уже существующей БД)
        cols = [r["name"] for r in c.execute("PRAGMA table_info(players)")]
        if "banked" not in cols:
            c.execute("ALTER TABLE players ADD COLUMN banked INTEGER DEFAULT 0")


def register(user_id: int, username: str, name: str, stage: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO players(user_id, username, name, stage, started_at) "
            "VALUES (?,?,?,?,?)",
            (user_id, username, name, stage, time.time()),
        )
        c.execute(
            "UPDATE players SET username=?, name=? WHERE user_id=?",
            (username, name, user_id),
        )


def get_player(user_id: int) -> Optional[sqlite3.Row]:
    with _conn() as c:
        return c.execute("SELECT * FROM players WHERE user_id=?", (user_id,)).fetchone()


def set_stage(user_id: int, stage: str) -> None:
    with _conn() as c:
        c.execute("UPDATE players SET stage=? WHERE user_id=?", (stage, user_id))


def add_score(user_id: int, delta: int) -> None:
    with _conn() as c:
        c.execute("UPDATE players SET score=score+? WHERE user_id=?", (delta, user_id))


def mark_finished(user_id: int) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE players SET finished_at=COALESCE(finished_at, ?) WHERE user_id=?",
            (time.time(), user_id),
        )


def add_banked(user_id: int, n: int = 1) -> int:
    """Начислить «подсказку» для грядущей Игры (награда за пройденный этап)."""
    with _conn() as c:
        c.execute(
            "UPDATE players SET banked=COALESCE(banked,0)+? WHERE user_id=?",
            (n, user_id),
        )
        row = c.execute("SELECT banked FROM players WHERE user_id=?", (user_id,)).fetchone()
        return row["banked"] if row else 0


def set_banked(user_id: int, n: int) -> int:
    with _conn() as c:
        c.execute("UPDATE players SET banked=? WHERE user_id=?", (n, user_id))
        return n


def find_by_username(username: str) -> Optional[int]:
    username = username.lstrip("@")
    with _conn() as c:
        row = c.execute(
            "SELECT user_id FROM players WHERE username=? COLLATE NOCASE", (username,)
        ).fetchone()
        return row["user_id"] if row else None


def add_submission(user_id: int, stage: str, kind: str, payload: str, file_id: Optional[str]) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO submissions(user_id, stage, kind, payload, file_id, ts) "
            "VALUES (?,?,?,?,?,?)",
            (user_id, stage, kind, payload, file_id, time.time()),
        )
        return cur.lastrowid


def get_submission(sub_id: int) -> Optional[sqlite3.Row]:
    with _conn() as c:
        return c.execute("SELECT * FROM submissions WHERE id=?", (sub_id,)).fetchone()


def set_submission_status(sub_id: int, status: str) -> None:
    with _conn() as c:
        c.execute("UPDATE submissions SET status=? WHERE id=?", (status, sub_id))


def pending() -> list[sqlite3.Row]:
    with _conn() as c:
        return c.execute(
            "SELECT s.*, p.username, p.name FROM submissions s "
            "JOIN players p ON p.user_id=s.user_id WHERE s.status='pending' "
            "ORDER BY s.ts"
        ).fetchall()


def all_players() -> list[sqlite3.Row]:
    with _conn() as c:
        return c.execute(
            "SELECT * FROM players ORDER BY (finished_at IS NULL), finished_at, started_at"
        ).fetchall()


def log_event(user_id: int, event: str, detail: str = "") -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO log(user_id, event, detail, ts) VALUES (?,?,?,?)",
            (user_id, event, detail, time.time()),
        )


def hint_used(user_id: int, stage: str) -> int:
    with _conn() as c:
        row = c.execute(
            "SELECT used FROM hints WHERE user_id=? AND stage=?", (user_id, stage)
        ).fetchone()
        return row["used"] if row else 0


def inc_hint(user_id: int, stage: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO hints(user_id, stage, used) VALUES (?,?,1) "
            "ON CONFLICT(user_id, stage) DO UPDATE SET used=used+1",
            (user_id, stage),
        )
