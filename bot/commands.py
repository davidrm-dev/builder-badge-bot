"""Menú de comandos que Telegram muestra en el botón "/" , en español e inglés."""

from __future__ import annotations

from telegram import BotCommand, BotCommandScopeDefault

COMMANDS = {
    "es": [
        ("hoy", "Misión de hoy"),
        ("badges", "Tablero de las 21 badges"),
        ("racha", "Estado de tus rachas"),
        ("sync", "Revisar si ganaste badges nuevas"),
        ("perfil", "Conectar tu perfil de Builder Center"),
        ("hora", "Hora del recordatorio diario"),
        ("zona", "Tu zona horaria"),
        ("idioma", "Español o inglés"),
        ("pausar", "Pausar recordatorios"),
        ("activar", "Reanudar recordatorios"),
        ("ayuda", "Guía rápida"),
    ],
    "en": [
        ("today", "Today's mission"),
        ("badges", "Board with the 21 badges"),
        ("streak", "Your streaks"),
        ("sync", "Check for new badges"),
        ("profile", "Connect your Builder Center profile"),
        ("time", "Daily reminder time"),
        ("timezone", "Your time zone"),
        ("language", "Spanish or English"),
        ("pause", "Pause reminders"),
        ("resume", "Resume reminders"),
        ("help", "Quick guide"),
    ],
}


async def register_commands(bot) -> None:
    """Menú en inglés por defecto y en español para clientes con locale es."""
    await bot.set_my_commands(
        [BotCommand(name, desc) for name, desc in COMMANDS["en"]],
        scope=BotCommandScopeDefault(),
    )
    await bot.set_my_commands(
        [BotCommand(name, desc) for name, desc in COMMANDS["es"]],
        scope=BotCommandScopeDefault(),
        language_code="es",
    )
