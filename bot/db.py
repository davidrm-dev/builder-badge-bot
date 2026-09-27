"""Persistencia en SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    chat_id     INTEGER PRIMARY KEY,
    alias       TEXT,
    bp_id       TEXT,
    name        TEXT,
    tz          TEXT NOT NULL DEFAULT 'America/Bogota',
    hour        INTEGER NOT NULL DEFAULT 9,
    minute      INTEGER NOT NULL DEFAULT 0,
    enabled     INTEGER NOT NULL DEFAULT 1,
    lang        TEXT NOT NULL DEFAULT 'es',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS badges (
    chat_id       INTEGER NOT NULL,
    badge_id      TEXT NOT NULL,
    badge_key     TEXT,
    display_name  TEXT,
    awarded_epoch REAL,
    PRIMARY KEY (chat_id, badge_id)
);
CREATE TABLE IF NOT EXISTS checkins (
    chat_id   INTEGER NOT NULL,
    day       TEXT NOT NULL,
    task      TEXT NOT NULL,
    synthetic INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, day, task)
);
CREATE TABLE IF NOT EXISTS tiers (
    chat_id INTEGER NOT NULL,
    tier    INTEGER NOT NULL,
    PRIMARY KEY (chat_id, tier)
);
"""


@dataclass
class User:
    chat_id: int
    alias: str | None
    bp_id: str | None
    name: str | None
    tz: str
    hour: int
    minute: int
    enabled: bool
    lang: str = "es"


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(users)")}
        if "lang" not in cols:
            self._conn.execute("ALTER TABLE users ADD COLUMN lang TEXT NOT NULL DEFAULT 'es'")
        checkin_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(checkins)")}
        if "synthetic" not in checkin_cols:
            self._conn.execute("ALTER TABLE checkins ADD COLUMN synthetic INTEGER NOT NULL DEFAULT 0")

    # ---------------- usuarios ----------------
    def ensure_user(self, chat_id: int) -> User:
        self._conn.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))
        self._conn.commit()
        user = self.get_user(chat_id)
        assert user is not None
        return user

    def get_user(self, chat_id: int) -> User | None:
        row = self._conn.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
        return self._to_user(row) if row else None

    def all_users(self) -> list[User]:
        rows = self._conn.execute("SELECT * FROM users").fetchall()
        return [self._to_user(r) for r in rows]

    @staticmethod
    def _to_user(row: sqlite3.Row) -> User:
        return User(
            chat_id=row["chat_id"],
            alias=row["alias"],
            bp_id=row["bp_id"],
            name=row["name"],
            tz=row["tz"],
            hour=row["hour"],
            minute=row["minute"],
            enabled=bool(row["enabled"]),
            lang=row["lang"],
        )

    def set_profile(self, chat_id: int, alias: str, bp_id: str, name: str) -> None:
        self.ensure_user(chat_id)
        self._conn.execute(
            "UPDATE users SET alias = ?, bp_id = ?, name = ? WHERE chat_id = ?",
            (alias, bp_id, name, chat_id),
        )
        self._conn.commit()

    def set_schedule(self, chat_id: int, hour: int, minute: int) -> None:
        self._conn.execute(
            "UPDATE users SET hour = ?, minute = ?, enabled = 1 WHERE chat_id = ?",
            (hour, minute, chat_id),
        )
        self._conn.commit()

    def set_lang(self, chat_id: int, lang: str) -> None:
        self.ensure_user(chat_id)
        self._conn.execute("UPDATE users SET lang = ? WHERE chat_id = ?", (lang, chat_id))
        self._conn.commit()

    def set_timezone(self, chat_id: int, tz: str) -> None:
        self._conn.execute("UPDATE users SET tz = ? WHERE chat_id = ?", (tz, chat_id))
        self._conn.commit()

    def set_enabled(self, chat_id: int, enabled: bool) -> None:
        self._conn.execute(
            "UPDATE users SET enabled = ? WHERE chat_id = ?", (1 if enabled else 0, chat_id)
        )
        self._conn.commit()

    def delete_user(self, chat_id: int) -> None:
        for table in ("users", "badges", "checkins", "tiers"):
            self._conn.execute(f"DELETE FROM {table} WHERE chat_id = ?", (chat_id,))
        self._conn.commit()

    # ---------------- badges ----------------
    def known_badge_ids(self, chat_id: int) -> set[str]:
        rows = self._conn.execute("SELECT badge_id FROM badges WHERE chat_id = ?", (chat_id,))
        return {r["badge_id"] for r in rows}

    def known_badge_keys(self, chat_id: int) -> set[str]:
        rows = self._conn.execute(
            "SELECT badge_key FROM badges WHERE chat_id = ? AND badge_key IS NOT NULL", (chat_id,)
        )
        return {r["badge_key"] for r in rows}

    def save_badge(
        self, chat_id: int, badge_id: str, badge_key: str | None, display_name: str, epoch: float | None
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO badges (chat_id, badge_id, badge_key, display_name, awarded_epoch)"
            " VALUES (?, ?, ?, ?, ?)",
            (chat_id, badge_id, badge_key, display_name, epoch),
        )
        self._conn.commit()

    def badge_count(self, chat_id: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM badges WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return int(row["n"])

    def pending_tiers(self, chat_id: int, count: int, tiers: list[int]) -> list[int]:
        already = {
            r["tier"] for r in self._conn.execute("SELECT tier FROM tiers WHERE chat_id = ?", (chat_id,))
        }
        new = [t for t in tiers if count >= t and t not in already]
        for tier in new:
            self._conn.execute("INSERT OR IGNORE INTO tiers (chat_id, tier) VALUES (?, ?)", (chat_id, tier))
        self._conn.commit()
        return new

    # ---------------- check-ins ----------------
    def add_checkin(self, chat_id: int, day: date, task: str) -> bool:
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO checkins (chat_id, day, task) VALUES (?, ?, ?)",
            (chat_id, day.isoformat(), task),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def remove_checkin(self, chat_id: int, day: date, task: str) -> None:
        self._conn.execute(
            "DELETE FROM checkins WHERE chat_id = ? AND day = ? AND task = ?",
            (chat_id, day.isoformat(), task),
        )
        self._conn.commit()

    def tasks_done(self, chat_id: int, day: date) -> set[str]:
        rows = self._conn.execute(
            "SELECT task FROM checkins WHERE chat_id = ? AND day = ?", (chat_id, day.isoformat())
        )
        return {r["task"] for r in rows}

    def days_with_task(self, chat_id: int, task: str) -> set[date]:
        rows = self._conn.execute(
            "SELECT day FROM checkins WHERE chat_id = ? AND task = ?", (chat_id, task)
        )
        return {date.fromisoformat(r["day"]) for r in rows}

    def set_streak(self, chat_id: int, task: str, days: int, today: date) -> None:
        """Ajusta la racha de `task` a `days` días rellenando hacia atrás con check-ins sintéticos.

        - Borra los check-ins sintéticos de hoy hacia atrás (limpia un ajuste previo).
        - Inserta check-ins sintéticos en los `days` días que terminan hoy, incluido hoy: la
          racha declarada cuenta el día actual, y sin él la cadena se rompe mañana.
        - No toca los check-ins reales (synthetic=0) del usuario.
        """
        # 1. Borrar sintéticos previos para empezar limpio
        self._conn.execute(
            "DELETE FROM checkins WHERE chat_id = ? AND task = ? AND day <= ? AND synthetic = 1",
            (chat_id, task, today.isoformat()),
        )
        # 2. Insertar sintéticos para los días que falten
        for offset in range(days):
            day = today - timedelta(days=offset)
            self._conn.execute(
                "INSERT OR IGNORE INTO checkins (chat_id, day, task, synthetic) VALUES (?, ?, ?, 1)",
                (chat_id, day.isoformat(), task),
            )
        self._conn.commit()

    def reset_streak(self, chat_id: int, task: str, today: date) -> None:
        """Reinicia la racha borrando todos los check-ins sintéticos de hoy hacia atrás."""
        self._conn.execute(
            "DELETE FROM checkins WHERE chat_id = ? AND task = ? AND day <= ? AND synthetic = 1",
            (chat_id, task, today.isoformat()),
        )
        self._conn.commit()

    def daily_streak(self, chat_id: int, task: str, today: date) -> int:
        """Días consecutivos con el task hecho, contando hasta hoy (o ayer si hoy falta)."""
        days = self.days_with_task(chat_id, task)
        if not days:
            return 0
        cursor = today if today in days else today - timedelta(days=1)
        streak = 0
        while cursor in days:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    def weekly_streak(self, chat_id: int, task: str, today: date) -> int:
        """Semanas consecutivas (lunes-domingo) con al menos un registro del task."""
        days = self.days_with_task(chat_id, task)
        if not days:
            return 0
        weeks = {d - timedelta(days=d.weekday()) for d in days}
        current = today - timedelta(days=today.weekday())
        cursor = current if current in weeks else current - timedelta(days=7)
        streak = 0
        while cursor in weeks:
            streak += 1
            cursor -= timedelta(days=7)
        return streak
