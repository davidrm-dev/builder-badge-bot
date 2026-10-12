"""Lógica compartida por todos los canales (Telegram, correo): store, zona horaria y sync."""

from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import badges as cat
from . import builder_api as api
from .db import Store, User

DB_PATH = os.environ.get("BOT_DB_PATH", "data/bot.sqlite3")
DEFAULT_TZ = os.environ.get("BOT_DEFAULT_TZ", "America/Bogota")

_store = None


def build_store():
    """DynamoDB si corre en Lambda (BOT_TABLE), SQLite en local/VM."""
    if os.environ.get("BOT_TABLE"):
        from .dynamo import DynamoStore

        return DynamoStore()
    return Store(DB_PATH)


def get_store():
    """Store único por proceso, compartido entre canales."""
    global _store
    if _store is None:
        _store = build_store()
    return _store


def user_tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.tz)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TZ)


def today_for(user: User) -> date:
    return datetime.now(user_tz(user)).date()


def valid_tz(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def hhmm(user: User) -> str:
    return f"{user.hour:02d}:{user.minute:02d}"


def sync_badges(store, uid: int, notify_new: bool = True) -> tuple[list[str], int, list[int]]:
    """Trae las badges desde la API y devuelve (nuevas, total, tiers nuevos)."""
    user = store.get_user(uid)
    if not user or not user.bp_id:
        return [], 0, []
    awarded = api.get_awarded_badges(user.bp_id)
    known = store.known_badge_ids(uid)
    new_names = []
    for badge in awarded:
        match = cat.match(badge.badge_id, badge.display_name)
        if badge.badge_id not in known:
            new_names.append(badge.display_name or badge.badge_id)
        store.save_badge(
            uid,
            badge.badge_id,
            match.key if match else None,
            badge.display_name,
            badge.awarded_epoch,
        )
    total = store.badge_count(uid)
    tiers = store.pending_tiers(uid, total, list(cat.TIER_VALUES))
    if not notify_new:
        return [], total, []
    return new_names, total, tiers
