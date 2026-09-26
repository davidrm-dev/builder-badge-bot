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
