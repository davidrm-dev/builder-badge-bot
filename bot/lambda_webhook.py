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

# La app y su event loop se crean una vez y se reutilizan entre invocaciones warm: el cliente
# HTTP de python-telegram-bot queda atado al loop donde se inicializó, así que cerrarlo por
# invocación rompería la siguiente con "Event loop is closed".
_app = None
_loop: asyncio.AbstractEventLoop | None = None


def _get_app():
    global _app, _loop
    if _app is None or _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        app = build_app(telegram_token(), with_jobs=False)
        _loop.run_until_complete(app.initialize())
        _app = app
    return _app


def _reset() -> None:
    global _app, _loop
    _app = None
    if _loop is not None and not _loop.is_closed():
        _loop.close()
    _loop = None


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
    try:
        _loop.run_until_complete(app.process_update(update))
    except RuntimeError:  # loop en estado inválido: se reconstruye para la siguiente invocación
        log.exception("Loop inválido, reiniciando la app")
        _reset()
    return {"statusCode": 200, "body": "ok"}
