"""Lambda detrás de una Function URL: recibe los updates del webhook de Telegram."""

from __future__ import annotations

import asyncio
import base64
import json
import logging

from telegram import Update

from .config import telegram_token, webhook_secret
from .main import build_app

log = logging.getLogger("builder-badge-bot.webhook")

_loop = asyncio.new_event_loop()
_app = None


def _get_app():
    global _app
    if _app is None:
        _app = build_app(telegram_token(), with_jobs=False)
        _loop.run_until_complete(_app.initialize())
    return _app


def _body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    return json.loads(raw)


def handler(event: dict, context: object) -> dict:
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    expected = webhook_secret()
    if expected and headers.get("x-telegram-bot-api-secret-token") != expected:
        return {"statusCode": 403, "body": "forbidden"}

    app = _get_app()
    update = Update.de_json(_body(event), app.bot)
    _loop.run_until_complete(app.process_update(update))
    return {"statusCode": 200, "body": "ok"}
