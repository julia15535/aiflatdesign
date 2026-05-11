"""Работа с SQLite базой данных.

Три таблицы:
- users — Telegram пользователи + статус онбординга
- sessions — каждое обращение к боту (фото, размеры, объект)
- generations — пока пусто (заполнится в Шагах 3-4 при реальной генерации)

Подробнее: .memory_bank/domain/data_model.md
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def _db_path() -> Path:
    data_dir = Path(os.environ.get("DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "prototype.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Создаёт таблицы если их ещё нет. Идемпотентно."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                tg_user_id INTEGER PRIMARY KEY,
                username TEXT,
                onboarded INTEGER NOT NULL DEFAULT 0,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_generations INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_user_id INTEGER NOT NULL,
                scene_url TEXT,
                product_url TEXT,
                target_class TEXT,
                room_dims_m TEXT,
                product_dims_cm TEXT,
                scene_quality_json TEXT,
                product_quality_json TEXT,
                scene_analysis_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                success INTEGER NOT NULL,
                error_type TEXT,
                result_url TEXT,
                variants_json TEXT,
                validation_json TEXT,
                size_check_json TEXT,
                wow_score REAL,
                cost_usd REAL,
                duration_sec INTEGER,
                user_rating TEXT,
                user_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_user
                ON sessions(tg_user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_generations_session
                ON generations(session_id, created_at);
        """)
    logger.info("БД инициализирована: %s", _db_path())


def touch_user(tg_user_id: int, username: str | None) -> None:
    """Записать факт обращения пользователя. Создаёт запись если её нет."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (tg_user_id, username, last_seen)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(tg_user_id) DO UPDATE SET
                username = excluded.username,
                last_seen = CURRENT_TIMESTAMP
            """,
            (tg_user_id, username),
        )


def is_user_onboarded(tg_user_id: int) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT onboarded FROM users WHERE tg_user_id = ?",
            (tg_user_id,),
        ).fetchone()
    return bool(row and row["onboarded"])


def mark_user_onboarded(tg_user_id: int, username: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (tg_user_id, username, onboarded)
            VALUES (?, ?, 1)
            ON CONFLICT(tg_user_id) DO UPDATE SET
                onboarded = 1,
                last_seen = CURRENT_TIMESTAMP
            """,
            (tg_user_id, username),
        )


def log_session(
    tg_user_id: int,
    scene_url: str | None = None,
    product_url: str | None = None,
    target_class: str | None = None,
    room_dims_m: tuple[float, float] | None = None,
    product_dims_cm: tuple[float, float, float] | None = None,
    scene_quality: dict | None = None,
    product_quality: dict | None = None,
    scene_analysis: dict | None = None,
) -> int:
    """Сохранить сессию пользователя. Возвращает id новой записи."""
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO sessions
                (tg_user_id, scene_url, product_url, target_class,
                 room_dims_m, product_dims_cm,
                 scene_quality_json, product_quality_json, scene_analysis_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tg_user_id,
                scene_url,
                product_url,
                target_class,
                json.dumps(list(room_dims_m)) if room_dims_m else None,
                json.dumps(list(product_dims_cm)) if product_dims_cm else None,
                json.dumps(scene_quality) if scene_quality else None,
                json.dumps(product_quality) if product_quality else None,
                json.dumps(scene_analysis) if scene_analysis else None,
            ),
        )
        return int(cur.lastrowid or 0)


def count_recent_generations(tg_user_id: int, hours: int = 24) -> int:
    """Сколько успешных генераций пользователь сделал за последние N часов.
    Для лимита 5/день."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM generations g
            JOIN sessions s ON s.id = g.session_id
            WHERE s.tg_user_id = ?
              AND g.success = 1
              AND g.created_at >= datetime('now', ?)
            """,
            (tg_user_id, f"-{hours} hours"),
        ).fetchone()
    return int(row["cnt"]) if row else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print(f"OK: БД создана в {_db_path()}")
