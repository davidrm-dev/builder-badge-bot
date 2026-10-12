"""Canal de correo: tokens firmados, páginas web y envío diario, sin tocar SES ni la API real."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import pytest

from bot import builder_api as api
from bot import core, web
from bot import email_channel as mail
from bot import lambda_scheduler as sched
from bot.db import Store

BASE = "https://coach.example"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL_LINK_SECRET", "test-secret")
    monkeypatch.setenv("EMAIL_FROM", "Coach <coach@example.com>")
    store = Store(tmp_path / "email.sqlite3")
    monkeypatch.setattr(core, "_store", store)
    monkeypatch.setattr(
        api,
        "get_profile",
        lambda alias: api.Profile(alias="davidrm", builder_profile_id="bp-1", name="David"),
    )
    monkeypatch.setattr(api, "get_awarded_badges", lambda bp_id: [])
    outbox: list[tuple[str, mail.Email]] = []
    monkeypatch.setattr(mail, "send", lambda to, email: outbox.append((to, email)))
    return store, outbox


def _token(url: str) -> str:
    return url.split("?t=", 1)[1]


def _signup(email: str = "Dev@Example.com", **extra: str) -> tuple[int, str]:
    form = {"email": email, "alias": "davidrm", "time": "07:30", "tz": "America/Lima", "lang": "es"}
    form.update(extra)
    return web.route("POST", "/signup", form, {}, BASE)


def _confirm(outbox) -> None:
    url = next(u for u in outbox[-1][1].text.split() if "/confirm?t=" in u)
    status, _ = web.route("GET", "/confirm", {"t": _token(url)}, {}, BASE)
    assert status == 200


# ------------------------------------------------------------------ tokens
def test_tokens_roundtrip_and_reject_tampering(env):
    token = mail.sign("checkin", -123, "2026-10-12:visit")
    assert mail.verify(token, "checkin") == (-123, "2026-10-12:visit")
    with pytest.raises(mail.BadToken):
        mail.verify(token, "unsub")  # otra acción
    _body, mac = token.split(".")
    forged = mail.sign("checkin", -999, "2026-10-12:visit").split(".")[0] + "." + mac
    with pytest.raises(mail.BadToken):
        mail.verify(forged, "checkin")
    with pytest.raises(mail.BadToken):
        mail.verify(token, "checkin", now=time.time() + 3 * mail.DAY)  # vencido


def test_unsubscribe_token_never_expires(env):
    token = mail.sign("unsub", -1)
    assert mail.verify(token, "unsub", now=time.time() + 5 * 365 * mail.DAY) == (-1, "")


def test_markdown_is_escaped_and_converted():
    assert mail.md_to_html("*Hola* <b>_x_</b> `y`\nz") == (
        '<strong>Hola</strong> &lt;b&gt;<em>x</em>&lt;/b&gt; <code style="font-family:monospace">y</code><br>z'
    )
    assert mail.md_to_text("*Hola* _x_ `y`") == "Hola x y"


# ------------------------------------------------------------------ inscripción
def test_signup_creates_paused_user_and_sends_confirmation(env):
    store, outbox = env
    status, body = _signup()
    assert status == 200 and "dev@example.com" in body
    user = store.get_user_by_email("dev@example.com")
    assert user.chat_id < 0 and not user.enabled
    assert (user.hour, user.minute, user.tz, user.alias) == (7, 30, "America/Lima", "davidrm")
    assert outbox[-1][0] == "dev@example.com"
    assert "Confirma" in outbox[-1][1].subject

    _confirm(outbox)
    assert store.get_user(user.chat_id).enabled


def test_signup_rejects_bad_email_and_unknown_alias(env, monkeypatch):
    _store, outbox = env
    assert _signup(email="no-es-correo")[0] == 400

    def not_found(alias):
        raise api.ProfileNotFound(alias)

    monkeypatch.setattr(api, "get_profile", not_found)
    status, body = _signup()
    assert status == 400 and "No encontré" in body
    assert outbox == []


def test_signup_does_not_overwrite_existing_user_and_throttles(env):
    store, outbox = env
    _signup()
    _confirm(outbox)
    status, _ = _signup(time="22:00")  # alguien repite el correo con otros datos
    assert status == 200
    user = store.get_user_by_email("dev@example.com")
    assert (user.hour, user.minute) == (7, 30)
    assert len(outbox) == 1  # el reenvío cae dentro de la ventana anti-spam


def test_honeypot_sends_nothing(env):
    store, outbox = env
    assert _signup(website="spam")[0] == 200
    assert outbox == [] and store.get_user_by_email("dev@example.com") is None


# ------------------------------------------------------------------ correo diario y check-in
def _active_user(env):
    store, outbox = env
    _signup()
    _confirm(outbox)
    outbox.clear()
    return store.get_user_by_email("dev@example.com")


def test_daily_email_is_short_with_checkin_links_and_unsubscribe(env):
    store, outbox = env
    user = _active_user(env)
    mail.send_daily(store, user, BASE)
    to, email = outbox[-1]
    assert to == "dev@example.com"
    assert "1/21" not in email.subject and "0/21" in email.subject
    assert email.html.count("/c?t=") == 6  # 4 diarias + 2 semanales pendientes
    assert email.unsubscribe.startswith(f"{BASE}/u?t=")
    assert "<script" not in email.html
    assert "🎯 Hello, World!" in email.html and "https://builder.aws.com/profile" in email.text
    assert "profile?tab=badges#activity" in email.text


def test_checkin_get_only_prompts_post_marks_and_is_idempotent(env):
    store, _ = env
    user = _active_user(env)
    day = core.today_for(user)
    token = mail.sign("checkin", user.chat_id, mail.checkin_extra(day, "visit"))

    status, body = web.route("GET", "/c", {"t": token}, {}, BASE)
    assert status == 200 and 'method="post"' in body
    assert store.tasks_done(user.chat_id, day) == set()  # los escáneres de enlaces no marcan

    for _ in range(2):
        status, body = web.route("POST", "/c", {"t": token}, {}, BASE)
        assert status == 200 and "1/7" in body
    assert store.tasks_done(user.chat_id, day) == {"visit"}


def test_old_checkin_link_is_refused(env):
    store, _ = env
    user = _active_user(env)
    old = core.today_for(user) - timedelta(days=2)
    token = mail.sign("checkin", user.chat_id, mail.checkin_extra(old, "visit"), now=time.time())
    _status, body = web.route("POST", "/c", {"t": token}, {}, BASE)
    assert "ya pasó" in body
    assert store.tasks_done(user.chat_id, old) == set()


# ------------------------------------------------------------------ ajustes y baja
def test_settings_update_and_delete(env):
    store, _ = env
    user = _active_user(env)
    token = mail.sign("me", user.chat_id)
    status, body = web.route("GET", "/me", {"t": token}, {}, BASE)
    assert status == 200 and "Tus 21 badges" in body

    form = {"t": token, "op": "save", "time": "06:05", "tz": "Europe/Madrid", "lang": "en"}
    status, body = web.route("POST", "/me", form, {}, BASE)
    user = store.get_user(user.chat_id)
    assert (user.hour, user.minute, user.tz, user.lang, user.enabled) == (6, 5, "Europe/Madrid", "en", False)
    assert "Saved" in body

    web.route("POST", "/me", {"t": token, "op": "delete"}, {}, BASE)
    assert store.get_user(user.chat_id) is None
    assert store.get_user_by_email("dev@example.com") is None


def test_one_click_unsubscribe(env):
    store, _ = env
    user = _active_user(env)
    token = mail.sign("unsub", user.chat_id)
    web.route("GET", "/u", {"t": token}, {}, BASE)
    assert store.get_user(user.chat_id).enabled  # el GET solo pregunta
    web.route("POST", "/u", {"t": token, "List-Unsubscribe": "One-Click"}, {}, BASE)
    assert not store.get_user(user.chat_id).enabled


def test_invalid_token_pages(env):
    for path in ("/confirm", "/me", "/u"):
        status, body = web.route("GET", path, {"t": "basura"}, {}, BASE)
        assert status == 400 and "no es válido" in body


def test_lambda_handler_parses_function_url_event(env):
    event = {
        "rawPath": "/",
        "rawQueryString": "lang=en",
        "headers": {"Accept-Language": "es-CO"},
        "requestContext": {"http": {"method": "GET"}, "domainName": "abc.lambda-url.us-east-1.on.aws"},
    }
    resp = web.handler(event, None)
    assert resp["statusCode"] == 200
    assert "Sign me up" in resp["body"]
    assert resp["headers"]["referrer-policy"] == "no-referrer"


# ------------------------------------------------------------------ scheduler
def test_scheduler_sends_email_once_per_day(env, monkeypatch):
    store, outbox = env
    user = _active_user(env)
    monkeypatch.setenv("PUBLIC_BASE_URL", BASE)
    monkeypatch.delenv("TOKEN_PARAMETER", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    now = datetime.now(core.user_tz(user))
    store.set_schedule(user.chat_id, now.hour, now.minute)
    store.ensure_user(77)  # usuario de Telegram sin token configurado: se salta

    import asyncio

    assert asyncio.run(sched._run()) == 1
    assert asyncio.run(sched._run()) == 0  # ya se mandó hoy
    assert len(outbox) == 1
    assert store.last_daily_sent(user.chat_id) == now.date().isoformat()


def test_finished_user_gets_final_email_and_is_paused(env, monkeypatch):
    store, outbox = env
    user = _active_user(env)
    from bot import badges as cat

    # La API es la fuente de verdad del sync: las 21 tienen que venir de ahí.
    awarded = [
        api.AwardedBadge(
            badge_id=f"id-{i}",
            display_name=badge.name,
            description="",
            category="",
            awarded_epoch=None,
        )
        for i, badge in enumerate(cat.CATALOG)
    ]
    monkeypatch.setattr(api, "get_awarded_badges", lambda bp_id: awarded)
    mail.send_daily(store, user, BASE)
    assert "21" in outbox[-1][1].subject
    assert not store.get_user(user.chat_id).enabled


def test_today_is_a_real_date(env):
    user = _active_user(env)
    assert isinstance(core.today_for(user), date)
