"""Lambda disparada por EventBridge Scheduler: manda el recordatorio a quien le toca.

Corre cada N minutos (15 por defecto) y revisa la hora local de cada usuario, así el
bot respeta la zona horaria de cada quien sin crear un schedule por usuario. Cada usuario
recibe la misión por su canal: Telegram o correo.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from datetime import datetime

from botocore.exceptions import ClientError

from . import email_channel
from .config import public_base_url, telegram_configured
from .core import get_store, user_tz

log = logging.getLogger("builder-badge-bot.scheduler")
WINDOW_MIN = int(os.environ.get("SCHEDULE_WINDOW_MINUTES", "15"))
RETRIES = 3
RETRY_BASE_SECONDS = 2.0


async def _retry(call, what: str):
    """Reintenta los cortes de red con Telegram (TimedOut es subclase de NetworkError)."""
    from telegram.error import NetworkError

    for attempt in range(1, RETRIES + 1):
        try:
            return await call()
        except NetworkError as exc:
            if attempt == RETRIES:
                raise
            delay = RETRY_BASE_SECONDS * 2 ** (attempt - 1)
            log.warning("%s falló (%s), reintento %d en %.0fs", what, exc, attempt, delay)
            await asyncio.sleep(delay)


def _due(user, now: datetime) -> bool:
    minutes_now = now.hour * 60 + now.minute
    user_min = user.hour * 60 + user.minute
    # Aritmética modular para manejar el rollover de medianoche
    # (ej. usuario a las 23:55, scheduler corre a las 00:05 → delta=10, correcto)
    delta = (minutes_now - user_min) % 1440
    return delta < WINDOW_MIN


async def _run() -> int:
    store = get_store()
    sent, failed = 0, 0
    async with contextlib.AsyncExitStack() as stack:
        bot = None  # Telegram se inicializa solo si hay a quién escribirle por ahí
        for user in store.all_users():
            if not user.enabled or not user.bp_id:
                continue
            now = datetime.now(user_tz(user))
            if not _due(user, now) or store.last_daily_sent(user.chat_id) == now.date().isoformat():
                continue
            if user.channel == "email":
                base = public_base_url()
                if not base:
                    log.error("Falta PUBLIC_BASE_URL: no puedo armar enlaces para %s", user.chat_id)
                    continue
                try:
                    email_channel.send_daily(store, user, base)
                except ClientError as exc:
                    log.warning("SES rechazó el correo de %s: %s", user.chat_id, exc)
                    continue
            else:
                if not telegram_configured():
                    continue
                from telegram import Bot
                from telegram.error import Forbidden

                from .config import telegram_token
                from .main import send_daily

                try:
                    if bot is None:
                        candidate = Bot(telegram_token())
                        await _retry(candidate.initialize, "initialize")
                        stack.push_async_callback(candidate.shutdown)
                        bot = candidate
                    chat_id = user.chat_id
                    await _retry(lambda: send_daily(bot, chat_id), f"send_daily {chat_id}")
                except Forbidden:
                    log.warning("El usuario %s bloqueó el bot; lo pauso", user.chat_id)
                    store.set_enabled(user.chat_id, False)
                    continue
                except Exception:  # un usuario con problemas no debe dejar sin mensaje al resto
                    log.exception("No se pudo mandar el recordatorio a %s", user.chat_id)
                    failed += 1
                    continue
            store.mark_daily_sent(user.chat_id, now.date())
            sent += 1
    if failed:
        # Falla la invocación para que cuente en la métrica Errors (alarma) y Lambda la reintente;
        # los que ya recibieron su mensaje quedan marcados y no se repiten.
        raise RuntimeError(f"{failed} recordatorio(s) fallaron, {sent} enviados")
    return sent


def handler(event: dict, context: object) -> dict:
    sent = asyncio.run(_run())
    log.info("Recordatorios enviados: %d", sent)
    return {"sent": sent}
