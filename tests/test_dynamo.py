"""El store de DynamoDB debe comportarse igual que el de SQLite."""

from __future__ import annotations

from datetime import date, timedelta

import boto3
import pytest
from moto import mock_aws

from bot.dynamo import DynamoStore

TABLE = "badges-test"


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        boto3.resource("dynamodb").create_table(
            TableName=TABLE,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
        )
        yield DynamoStore(TABLE)


def test_perfil_horario_y_zona(store):
    user = store.ensure_user(1)
    assert user.hour == 9 and user.enabled
    store.set_profile(1, "davidrm", "bp-1", "David")
    store.set_schedule(1, 8, 30)
    store.set_timezone(1, "America/Lima")
    user = store.get_user(1)
    assert (user.alias, user.bp_id, user.hour, user.minute, user.tz) == (
        "davidrm",
        "bp-1",
        8,
        30,
        "America/Lima",
    )
    assert [u.chat_id for u in store.all_users()] == [1]


def test_badges_y_tiers(store):
    store.ensure_user(1)
    store.save_badge(1, "b1", "hello_world", "Hello, World!", 1700000000.0)
    store.save_badge(1, "b1", "hello_world", "Hello, World!", 1700000000.0)
    store.save_badge(1, "b2", None, "Otra", None)
    assert store.badge_count(1) == 2
    assert store.known_badge_ids(1) == {"b1", "b2"}
    assert store.known_badge_keys(1) == {"hello_world"}
    assert store.pending_tiers(1, 7, [7, 14, 21]) == [7]
    assert store.pending_tiers(1, 7, [7, 14, 21]) == []


def test_checkins_y_rachas(store):
    store.ensure_user(1)
    today = date(2026, 3, 10)
    for offset in range(3):
        assert store.add_checkin(1, today - timedelta(days=offset), "visit")
    assert store.add_checkin(1, today, "visit") is False
    assert store.tasks_done(1, today) == {"visit"}
    assert store.daily_streak(1, "visit", today) == 3
    assert store.weekly_streak(1, "visit", today) == 2
    store.remove_checkin(1, today, "visit")
    assert store.tasks_done(1, today) == set()


def test_marcas_de_envio_y_borrado(store):
    store.ensure_user(1)
    assert store.last_daily_sent(1) is None
    store.mark_daily_sent(1, date(2026, 3, 10))
    assert store.last_daily_sent(1) == "2026-03-10"
    store.save_badge(1, "b1", None, "Otra", None)
    store.delete_user(1)
    assert store.get_user(1) is None and store.badge_count(1) == 0

def test_ajuste_de_racha_sobrevive_al_dia_siguiente(store):
    store.ensure_user(1)
    today = date(2026, 3, 10)
    store.set_streak(1, "visit", 5, today)
    assert store.daily_streak(1, "visit", today) == 5
    assert store.daily_streak(1, "visit", today + timedelta(days=1)) == 5
    store.reset_streak(1, "visit", today)
    assert store.daily_streak(1, "visit", today) == 0
