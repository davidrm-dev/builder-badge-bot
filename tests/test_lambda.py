"""Las Lambdas: el webhook reutiliza su event loop y el scheduler respeta la medianoche."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from telegram.error import TimedOut

from bot import lambda_scheduler as sched
from bot import lambda_webhook as webhook


class FakeApp:
    def __init__(self) -> None:
        self.bot = None
        self.loops: list[asyncio.AbstractEventLoop] = []

    async def initialize(self) -> None:
        self.loops.append(asyncio.get_running_loop())

    async def process_update(self, update) -> None:
        self.loops.append(asyncio.get_running_loop())


@pytest.fixture()
def fake_webhook(monkeypatch):
    app = FakeApp()
    monkeypatch.setattr(webhook, "_app", None)
    monkeypatch.setattr(webhook, "_loop", None)
    monkeypatch.setattr(webhook, "telegram_token", lambda: "token")
    monkeypatch.setattr(webhook, "webhook_secret", lambda: "s3cret")
    monkeypatch.setattr(webhook, "build_app", lambda token, with_jobs=False: app)
    monkeypatch.setattr(webhook.Update, "de_json", staticmethod(lambda data, bot: data))
    return app


def _event() -> dict:
    return {
        "headers": {"X-Telegram-Bot-Api-Secret-Token": "s3cret"},
        "body": json.dumps({"update_id": 1}),
    }


def test_webhook_rejects_wrong_secret(fake_webhook):
    event = _event()
    event["headers"]["X-Telegram-Bot-Api-Secret-Token"] = "otro"
    assert webhook.handler(event, None)["statusCode"] == 403


def test_webhook_reuses_the_same_loop(fake_webhook):
    assert webhook.handler(_event(), None)["statusCode"] == 200
    assert webhook.handler(_event(), None)["statusCode"] == 200
    assert len(set(fake_webhook.loops)) == 1
    assert not fake_webhook.loops[0].is_closed()


@pytest.mark.parametrize(
    ("hour", "minute", "now", "due"),
    [
        (8, 0, "08:05", True),
        (8, 0, "08:20", False),
        (23, 55, "00:05", True),
        (0, 5, "23:55", False),
    ],
)
def test_due_handles_midnight_rollover(hour, minute, now, due):
    tz = ZoneInfo("America/Bogota")
    h, m = (int(x) for x in now.split(":"))
    moment = datetime(2026, 1, 2, h, m, tzinfo=tz)
    user = SimpleNamespace(hour=hour, minute=minute)
    assert sched._due(user, moment) is due


class FakeBot:
    def __init__(self, init_failures: int = 0) -> None:
        self.init_failures = init_failures
        self.init_calls = 0
        self.closed = False

    async def initialize(self) -> None:
        self.init_calls += 1
        if self.init_calls <= self.init_failures:
            raise TimedOut()

    async def shutdown(self) -> None:
        self.closed = True


class FakeStore:
    def __init__(self, users) -> None:
        self.users = users
        self.sent: list[int] = []

    def all_users(self):
        return self.users

    def last_daily_sent(self, chat_id):
        return None

    def mark_daily_sent(self, chat_id, day) -> None:
        self.sent.append(chat_id)

    def set_enabled(self, chat_id, enabled) -> None:
        pass


def _user(chat_id: int):
    now = datetime.now(ZoneInfo("America/Bogota"))
    return SimpleNamespace(
        chat_id=chat_id,
        enabled=True,
        bp_id="bp",
        channel="telegram",
        hour=now.hour,
        minute=now.minute,
    )


@pytest.fixture()
def fake_sched(monkeypatch):
    def setup(bot, users, send):
        import telegram

        from bot import config, main

        store = FakeStore(users)
        monkeypatch.setattr(telegram, "Bot", lambda token: bot)
        monkeypatch.setattr(config, "telegram_token", lambda: "token")
        monkeypatch.setattr(main, "send_daily", send)
        monkeypatch.setattr(sched, "get_store", lambda: store)
        monkeypatch.setattr(sched, "telegram_configured", lambda: True)
        monkeypatch.setattr(sched, "user_tz", lambda user: ZoneInfo("America/Bogota"))
        monkeypatch.setattr(sched, "RETRY_BASE_SECONDS", 0)
        return store

    return setup


def test_scheduler_retries_initialize_timeout(fake_sched):
    bot = FakeBot(init_failures=2)

    async def send(bot, chat_id):
        pass

    store = fake_sched(bot, [_user(1)], send)
    assert sched.handler({}, None) == {"sent": 1}
    assert bot.init_calls == 3
    assert store.sent == [1]
    assert bot.closed


def test_scheduler_gives_up_after_retries(fake_sched):
    bot = FakeBot(init_failures=sched.RETRIES)

    async def send(bot, chat_id):
        pass

    store = fake_sched(bot, [_user(1)], send)
    with pytest.raises(RuntimeError, match="1 recordatorio"):
        sched.handler({}, None)
    assert bot.init_calls == sched.RETRIES
    assert store.sent == []


def test_scheduler_one_failing_user_does_not_block_others(fake_sched):
    bot = FakeBot()
    calls: list[int] = []

    async def send(bot, chat_id):
        calls.append(chat_id)
        if chat_id == 1:
            raise TimedOut()

    store = fake_sched(bot, [_user(1), _user(2)], send)
    with pytest.raises(RuntimeError, match="1 recordatorio"):
        sched.handler({}, None)
    assert calls == [1, 1, 1, 2]
    assert store.sent == [2]
    assert bot.closed
