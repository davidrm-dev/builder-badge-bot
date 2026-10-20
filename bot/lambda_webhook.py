"""Lambda detrás de una Function URL.

Atiende tres cosas en la misma URL, sin API Gateway ni CloudFront:
    POST /          con el header secreto  → update del webhook de Telegram
    GET  /          → HTML de la Mini App
    POST /api/...   → API de la Mini App, autenticada con el initData de Telegram
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path

from telegram import Update

from . import miniapp
from .config import telegram_token, webhook_secret
from .main import build_app

log = logging.getLogger("builder-badge-bot.webhook")

WEBAPP_HTML = Path(__file__).resolve().parent.parent / "webapp" / "index.html"

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


def _json(status: int, payload: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json; charset=utf-8"},
        "body": json.dumps(payload, ensure_ascii=False),
    }


def handler(event: dict, context: object) -> dict:
    http = (event.get("requestContext") or {}).get("http") or {}
    method = (http.get("method") or "POST").upper()
    path = http.get("path") or "/"

    if method == "GET":
        return {
            "statusCode": 200,
            "headers": {
                "content-type": "text/html; charset=utf-8",
                "cache-control": "no-cache",
            },
            "body": WEBAPP_HTML.read_text(encoding="utf-8"),
        }

    if path.startswith("/api/"):
        status, payload = miniapp.handle(path, _body(event), telegram_token())
        return _json(status, payload)

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
