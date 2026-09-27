"""Las Lambdas: el webhook reutiliza su event loop y el scheduler respeta la medianoche."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

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
