"""Lambda disparada por EventBridge Scheduler: manda el recordatorio a quien le toca.

Corre cada N minutos (15 por defecto) y revisa la hora local de cada usuario, así el
bot respeta la zona horaria de cada quien sin crear un schedule por usuario.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

from telegram import Bot
from telegram.error import Forbidden

from .config import telegram_token
from .main import send_daily, store, user_tz

log = logging.getLogger("builder-badge-bot.scheduler")
WINDOW_MIN = int(os.environ.get("SCHEDULE_WINDOW_MINUTES", "15"))


def _due(user, now: datetime) -> bool:
    minutes_now = now.hour * 60 + now.minute
    user_min = user.hour * 60 + user.minute
    # Aritmética modular para manejar el rollover de medianoche
    # (ej. usuario a las 23:55, scheduler corre a las 00:05 → delta=10, correcto)
    delta = (minutes_now - user_min) % 1440
    return delta < WINDOW_MIN


async def _run() -> int:
    bot = Bot(telegram_token())
    async with bot:
        sent = 0
        for user in store.all_users():
            if not user.enabled or not user.bp_id:
                continue
            now = datetime.now(user_tz(user))
            if not _due(user, now) or store.last_daily_sent(user.chat_id) == now.date().isoformat():
                continue
            try:
                await send_daily(bot, user.chat_id)
                store.mark_daily_sent(user.chat_id, now.date())
                sent += 1
            except Forbidden:
                log.warning("El usuario %s bloqueó el bot; lo pauso", user.chat_id)
                store.set_enabled(user.chat_id, False)
        return sent


def handler(event: dict, context: object) -> dict:
    sent = asyncio.run(_run())
    log.info("Recordatorios enviados: %d", sent)
    return {"sent": sent}
