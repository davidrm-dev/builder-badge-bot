from datetime import date, timedelta

import pytest

from bot import badges as cat
from bot import coach
from bot.db import Store


@pytest.fixture()
def store(tmp_path):
    return Store(tmp_path / "test.sqlite3")


def test_catalog_has_21_unique_badges():
    assert cat.TOTAL == 21
    assert len({b.key for b in cat.CATALOG}) == 21


def test_match_by_api_id_and_by_display_name():
    assert cat.match("activity_badge.profile.about", "").key == "hello_world"
    assert cat.match("id.desconocido", "7-Day Like Streak").key == "like_7"
    assert cat.match("otro", "Badge Inventada") is None


def test_daily_streak_counts_consecutive_days(store):
    chat = 1
    store.ensure_user(chat)
    today = date(2026, 9, 26)
    for delta in (0, 1, 2, 4):
        store.add_checkin(chat, today - timedelta(days=delta), "visit")
    assert store.daily_streak(chat, "visit", today) == 3
    assert store.daily_streak(chat, "like", today) == 0


def test_daily_streak_tolerates_pending_today(store):
    chat = 2
    store.ensure_user(chat)
    today = date(2026, 9, 26)
    store.add_checkin(chat, today - timedelta(days=1), "like")
    store.add_checkin(chat, today - timedelta(days=2), "like")
    assert store.daily_streak(chat, "like", today) == 2


def test_weekly_streak(store):
    chat = 3
    store.ensure_user(chat)
    today = date(2026, 9, 26)
    for weeks in (0, 1, 2):
        store.add_checkin(chat, today - timedelta(weeks=weeks), "article_week")
    assert store.weekly_streak(chat, "article_week", today) == 3


def test_tiers_are_reported_once(store):
    chat = 4
    store.ensure_user(chat)
    assert store.pending_tiers(chat, 7, [7, 14, 21]) == [7]
    assert store.pending_tiers(chat, 7, [7, 14, 21]) == []
    assert store.pending_tiers(chat, 15, [7, 14, 21]) == [14]


def test_next_targets_prioritises_phase_and_one_badge_per_metric(store):
    earned = {b.key for b in cat.CATALOG if b.phase == 1}
    targets = coach.next_targets(earned, limit=3)
    metrics = [t.metric for t in targets]
    assert len(set(metrics)) == len(metrics)
    assert all(t.phase >= 2 for t in targets)
    assert targets[0].target == 7


def test_daily_message_marks_done_tasks(store):
    chat = 5
    store.ensure_user(chat)
    store.save_badge(chat, "activity_badge.profile.about", "hello_world", "Hello, World!", None)
    today = date(2026, 9, 26)
    store.add_checkin(chat, today, "visit")
    msg = coach.daily_message(store, chat, today)
    assert "1/21" in msg
    assert "✅ 🔑" in msg
    assert "⬜ ❤️" in msg


def test_badge_overview_lists_every_badge(store):
    chat = 6
    store.ensure_user(chat)
    overview = coach.badge_overview(store, chat)
    for badge in cat.CATALOG:
        assert badge.name in overview
    assert "0/21" in overview


# --------------------------------------------------------------------------- set_streak / reset_streak

def test_set_streak_fills_synthetic_checkins(store):
    chat = 10
    store.ensure_user(chat)
    today = date(2026, 9, 26)
    # Fijar racha de 5 días: los 5 días terminan hoy, incluido hoy
    store.set_streak(chat, "visit", 5, today)
    assert store.daily_streak(chat, "visit", today) == 5
    # Marcar hoy de verdad no la duplica
    store.add_checkin(chat, today, "visit")
    assert store.daily_streak(chat, "visit", today) == 5


def test_set_streak_does_not_overwrite_real_checkins(store):
    chat = 11
    store.ensure_user(chat)
    today = date(2026, 9, 26)
    # El usuario ya marcó ayer de verdad
    store.add_checkin(chat, today - timedelta(days=1), "visit")
    # Ajustar a 3 días: debería insertar sintéticos para días 2 y 3 hacia atrás
    store.set_streak(chat, "visit", 3, today)
    assert store.daily_streak(chat, "visit", today) == 3


def test_reset_streak_removes_only_synthetics(store):
    chat = 12
    store.ensure_user(chat)
    today = date(2026, 9, 26)
    # Real de hoy y sintéticos de ayer
    store.add_checkin(chat, today, "visit")
    store.set_streak(chat, "visit", 3, today)
    assert store.daily_streak(chat, "visit", today) == 3
    # Resetear: borra sintéticos pero conserva el check-in real de hoy
    store.reset_streak(chat, "visit", today)
    assert store.daily_streak(chat, "visit", today) == 1  # solo hoy queda


def test_set_streak_replaces_previous_adjustment(store):
    chat = 13
    store.ensure_user(chat)
    today = date(2026, 9, 26)
    store.set_streak(chat, "like", 10, today)
    assert store.daily_streak(chat, "like", today) == 10
    # Ajustar de nuevo a 3: los sintéticos viejos se borran y se crean nuevos
    store.set_streak(chat, "like", 3, today)
    assert store.daily_streak(chat, "like", today) == 3


def test_set_streak_survives_next_day(store):
    chat = 14
    store.ensure_user(chat)
    today = date(2026, 9, 26)
    store.set_streak(chat, "visit", 5, today)
    # Al día siguiente, sin marcar nada todavía, la racha sigue viva (no se reinicia a 0)
    assert store.daily_streak(chat, "visit", today + timedelta(days=1)) == 5
    store.add_checkin(chat, today + timedelta(days=1), "visit")
    assert store.daily_streak(chat, "visit", today + timedelta(days=1)) == 6


def test_todos_los_enlaces_del_catalogo_existen():
    """Cada badge y cada paso de la rutina apunta a una URL real del catálogo."""
    for badge in cat.CATALOG:
        assert badge.url.startswith(cat.BASE)
    for _task, _icon, _es, _en, link in cat.DAILY_ROUTINE + cat.WEEKLY_ROUTINE:
        assert link in cat.LINKS


def test_las_badges_de_perfil_llevan_a_la_pagina_de_perfil():
    """Bio y foto se editan en /profile, no en /settings (que solo tiene idioma y tema)."""
    for key in ("hello_world", "photo_finisher"):
        assert cat.BY_KEY[key].url == cat.LINKS["profile"]


def test_sincronizar_borra_las_insignias_que_ya_no_estan(monkeypatch, store, tmp_path):
    from bot import builder_api as api, main as botmain

    botmain.store = store
    store.set_profile(1, "davidrm", "bp-1", "David")
    store.save_badge(1, "vieja", None, "De otro perfil", 1.0)
    monkeypatch.setattr(
        api, "get_awarded_badges",
        lambda bp_id: [
            api.AwardedBadge(
                badge_id="activity_badge.profile.about",
                display_name="Hello, World!",
                description="",
                category="Getting Started",
                awarded_epoch=2.0,
            )
        ],
    )
    _new, total, _tiers = botmain.sync_badges(1, notify_new=False)
    assert total == 1
    assert store.known_badge_ids(1) == {"activity_badge.profile.about"}
