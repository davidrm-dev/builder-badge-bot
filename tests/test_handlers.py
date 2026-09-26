"""Smoke test: los handlers responden sin tocar Telegram ni la API real."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot import builder_api as api
from bot import main as botmain
from bot.db import Store


@pytest.fixture()
def env(tmp_path, monkeypatch):
    botmain.store = Store(tmp_path / "handlers.sqlite3")
    monkeypatch.setattr(
        api,
        "get_profile",
        lambda alias: api.Profile(alias="davidrm", builder_profile_id="bp-1", name="David"),
    )
    monkeypatch.setattr(
        api,
        "get_awarded_badges",
        lambda bp_id: [
            api.AwardedBadge(
                badge_id="activity_badge.profile.about",
                display_name="Hello, World!",
                description="",
                category="Getting Started",
                awarded_epoch=1.79e9,
            )
        ],
    )
    monkeypatch.setattr(botmain, "schedule_user", lambda application, user: None)
    return botmain.store


def fake_update() -> tuple[SimpleNamespace, AsyncMock]:
    reply = AsyncMock()
    message = SimpleNamespace(reply_text=reply, text="")
    return SimpleNamespace(effective_chat=SimpleNamespace(id=42), message=message), reply


def fake_context(*args: str) -> SimpleNamespace:
    return SimpleNamespace(args=list(args), application=SimpleNamespace())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "args", "expected"),
    [
        (botmain.cmd_start, (), "21 badges"),
        (botmain.cmd_profile, ("davidrm",), "Conectado"),
        (botmain.cmd_time, ("07:15",), "07:15"),
        (botmain.cmd_badges, (), "1/21"),
        (botmain.cmd_today, (), "Misión del día"),
        (botmain.cmd_sync, (), "Sin novedades"),
        (botmain.cmd_streak, (), "rachas"),
        (botmain.cmd_tz, ("America/Bogota",), "America/Bogota"),
        (botmain.cmd_pause, (), "pausados"),
        (botmain.cmd_resume, (), "Recordatorios activos"),
    ],
)
async def test_command_replies(env, handler, args, expected):
    update, reply = fake_update()
    await botmain.cmd_profile(update, fake_context("davidrm"))  # perfil conectado
    reply.reset_mock()
    await handler(update, fake_context(*args))
    sent = reply.await_args.args[0] if reply.await_args.args else reply.await_args.kwargs["text"]
    assert expected in sent


@pytest.mark.asyncio
async def test_profile_url_is_accepted(env):
    update, reply = fake_update()
    update.message.text = "https://builder.aws.com/community/@davidrm?tab=badges"
    await botmain.on_text(update, fake_context())
    sent = reply.await_args.args[0]
    assert "Conectado" in sent
    assert botmain.store.get_user(42).bp_id == "bp-1"


@pytest.mark.asyncio
async def test_bad_time_is_rejected(env):
    update, reply = fake_update()
    await botmain.cmd_time(update, fake_context("25:99"))
    assert "/hora 08:30" in reply.await_args.args[0]
