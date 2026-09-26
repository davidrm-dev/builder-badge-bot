"""Bot de Telegram que acompaña a un builder a completar las 21 badges de AWS Builder Center."""

from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import badges as cat
from . import builder_api as api
from . import coach
from .db import Store, User

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("builder-badge-bot")

DB_PATH = os.environ.get("BOT_DB_PATH", "data/bot.sqlite3")
DEFAULT_TZ = os.environ.get("BOT_DEFAULT_TZ", "America/Bogota")
store = Store(DB_PATH)

HELP = """*Comandos*
/perfil `alias` – conecta tu perfil de Builder Center (o pega la URL)
/badges – tu tablero con las 21 badges
/hoy – misión de hoy
/sync – revisa si ganaste badges nuevas
/racha – estado de tus rachas
/hora `HH:MM` – hora del recordatorio diario (ej. /hora 08:30)
/zona `Area/Ciudad` – tu zona horaria (ej. /zona America/Bogota)
/pausar – deja de recibir recordatorios
/activar – vuelve a recibirlos
/borrar – elimina tus datos

Ojo: AWS solo publica las badges *ya ganadas*, no el progreso interno de cada racha.
Por eso el bot lleva tu racha con los botones "hecho" de cada día y confirma las badges
contra la API pública de Builder Center."""


# --------------------------------------------------------------------------- utilidades
def user_tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.tz)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TZ)


def today_for(user: User) -> date:
    return datetime.now(user_tz(user)).date()


def routine_keyboard(chat_id: int, day: date) -> InlineKeyboardMarkup:
    done = store.tasks_done(chat_id, day)
    rows = []
    row = []
    for task, icon, _label in cat.DAILY_ROUTINE:
        mark = "✅" if task in done else "⬜"
        row.append(
            InlineKeyboardButton(
                f"{mark} {icon} {coach.TASK_LABEL[task]}", callback_data=f"done:{task}"
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    extra = []
    for task in ("article_week", "wish_vote_week"):
        mark = "✅" if task in done else "⬜"
        icon = "📝" if task == "article_week" else "💡"
        extra.append(
            InlineKeyboardButton(f"{mark} {icon} {coach.TASK_LABEL[task]}", callback_data=f"done:{task}")
        )
    rows.append(extra)
    rows.append([InlineKeyboardButton("🔄 Revisar badges", callback_data="sync")])
    return InlineKeyboardMarkup(rows)


def sync_badges(chat_id: int, notify_new: bool = True) -> tuple[list[str], int, list[int]]:
    """Trae las badges desde la API y devuelve (nuevas, total, tiers nuevos)."""
    user = store.get_user(chat_id)
    if not user or not user.bp_id:
        return [], 0, []
    awarded = api.get_awarded_badges(user.bp_id)
    known = store.known_badge_ids(chat_id)
    new_names = []
    for badge in awarded:
        match = cat.match(badge.badge_id, badge.display_name)
        if badge.badge_id not in known:
            new_names.append(badge.display_name or badge.badge_id)
        store.save_badge(
            chat_id,
            badge.badge_id,
            match.key if match else None,
            badge.display_name,
            badge.awarded_epoch,
        )
    total = store.badge_count(chat_id)
    tiers = store.pending_tiers(chat_id, total, sorted(cat.REWARD_TIERS))
    if not notify_new:
        return [], total, []
    return new_names, total, tiers


# --------------------------------------------------------------------------- scheduling
def schedule_user(app: Application, user: User) -> None:
    name = f"daily:{user.chat_id}"
    for job in app.job_queue.get_jobs_by_name(name):
        job.schedule_removal()
    if not user.enabled or not user.bp_id:
        return
    app.job_queue.run_daily(
        daily_job,
        time=time(hour=user.hour, minute=user.minute, tzinfo=user_tz(user)),
        name=name,
        chat_id=user.chat_id,
    )


async def daily_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.chat_id
    user = store.get_user(chat_id)
    if not user or not user.enabled:
        return
    try:
        new_names, total, tiers = sync_badges(chat_id)
    except api.BuilderApiError as exc:
        log.warning("sync falló para %s: %s", chat_id, exc)
        new_names, total, tiers = [], store.badge_count(chat_id), []
    if new_names:
        await context.bot.send_message(
            chat_id,
            coach.congrats_message(new_names, total, tiers),
            parse_mode=ParseMode.MARKDOWN,
        )
    day = today_for(user)
    if total >= cat.TOTAL:
        await context.bot.send_message(
            chat_id,
            "🏆 Ya tienes las 21 badges. Reclama tu voucher en Student Rewards y, si quieres, "
            "usa /pausar para dejar de recibir recordatorios.",
        )
        return
    await context.bot.send_message(
        chat_id,
        coach.daily_message(store, chat_id, day),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=routine_keyboard(chat_id, day),
    )


# --------------------------------------------------------------------------- comandos
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    store.ensure_user(chat_id)
    await update.message.reply_text(
        "👋 Soy tu coach para las *21 badges* de AWS Builder Center.\n\n"
        "1️⃣ Mándame tu usuario: `/perfil davidrm` (o pega la URL de tu perfil).\n"
        "2️⃣ Elige la hora del recordatorio: `/hora 08:00`.\n"
        "3️⃣ Cada día te digo exactamente qué hacer y marco tu racha.\n\n" + HELP,
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP, parse_mode=ParseMode.MARKDOWN)


async def set_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, alias: str) -> None:
    chat_id = update.effective_chat.id
    store.ensure_user(chat_id)
    try:
        profile = api.get_profile(alias)
    except api.ProfileNotFound:
        await update.message.reply_text(
            f"No encontré el perfil `{alias}` 🤔 Revisa el alias en la URL de tu perfil "
            "(builder.aws.com/community/@tualias).",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    except api.BuilderApiError as exc:
        await update.message.reply_text(f"Builder Center no respondió ({exc}). Intenta de nuevo.")
        return
    store.set_profile(chat_id, profile.alias, profile.builder_profile_id, profile.name)
    first_time = store.badge_count(chat_id) == 0
    try:
        _new_names, total, _tiers = sync_badges(chat_id, notify_new=not first_time)
    except api.BuilderApiError:
        total = store.badge_count(chat_id)
    user = store.get_user(chat_id)
    schedule_user(context.application, user)
    await update.message.reply_text(
        f"✅ Conectado: *{profile.name}* (@{profile.alias})\n"
        f"Detecté *{total}/{cat.TOTAL}* badges ganadas.\n"
        f"Recordatorio diario: *{user.hour:02d}:{user.minute:02d}* ({user.tz}) — cámbialo con /hora.\n\n"
        "Mira tu tablero con /badges o pide la misión de hoy con /hoy.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usa: `/perfil davidrm`", parse_mode=ParseMode.MARKDOWN)
        return
    await set_profile(update, context, context.args[0])


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    match = re.search(r"builder\.aws\.com/community/@([\w.\-]+)", text)
    if match:
        await set_profile(update, context, match.group(1))
        return
    if re.fullmatch(r"@?[\w.\-]{2,40}", text):
        await set_profile(update, context, text)
        return
    await update.message.reply_text("No te entendí 🙃 Escribe /ayuda para ver los comandos.")


def require_profile(update: Update) -> User | None:
    user = store.get_user(update.effective_chat.id)
    if not user or not user.bp_id:
        return None
    return user


async def cmd_badges(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = require_profile(update)
    if not user:
        await update.message.reply_text("Primero conecta tu perfil: `/perfil tualias`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        sync_badges(user.chat_id, notify_new=False)
    except api.BuilderApiError:
        pass
    await update.message.reply_text(
        coach.badge_overview(store, user.chat_id), parse_mode=ParseMode.MARKDOWN
    )


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = require_profile(update)
    if not user:
        await update.message.reply_text("Primero conecta tu perfil: `/perfil tualias`", parse_mode=ParseMode.MARKDOWN)
        return
    day = today_for(user)
    await update.message.reply_text(
        coach.daily_message(store, user.chat_id, day),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=routine_keyboard(user.chat_id, day),
    )


async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = require_profile(update)
    if not user:
        await update.message.reply_text("Primero conecta tu perfil: `/perfil tualias`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        new_names, total, tiers = sync_badges(user.chat_id)
    except api.BuilderApiError as exc:
        await update.message.reply_text(f"Builder Center no respondió ({exc}).")
        return
    if new_names:
        await update.message.reply_text(
            coach.congrats_message(new_names, total, tiers), parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            f"Sin novedades: sigues en *{total}/{cat.TOTAL}*. "
            "Las badges pueden tardar un rato en aparecer después de la acción.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def cmd_streak(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = require_profile(update)
    if not user:
        await update.message.reply_text("Primero conecta tu perfil: `/perfil tualias`", parse_mode=ParseMode.MARKDOWN)
        return
    day = today_for(user)
    earned = coach.earned_keys(store, user.chat_id)
    lines = coach.streak_lines(store, user.chat_id, day, earned)
    await update.message.reply_text(
        "*Tus rachas*\n" + ("\n".join(lines) if lines else "¡Ya tienes todas las badges de racha! 🔥"),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    store.ensure_user(chat_id)
    if not context.args or not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", context.args[0]):
        await update.message.reply_text("Usa: `/hora 08:30`", parse_mode=ParseMode.MARKDOWN)
        return
    hour, minute = (int(x) for x in context.args[0].split(":"))
    store.set_schedule(chat_id, hour, minute)
    user = store.get_user(chat_id)
    schedule_user(context.application, user)
    await update.message.reply_text(
        f"⏰ Listo, te escribo todos los días a las *{hour:02d}:{minute:02d}* ({user.tz}).",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_tz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    store.ensure_user(chat_id)
    if not context.args:
        await update.message.reply_text("Usa: `/zona America/Bogota`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        ZoneInfo(context.args[0])
    except (ZoneInfoNotFoundError, ValueError):
        await update.message.reply_text("Zona horaria inválida. Ejemplo: `America/Bogota`", parse_mode=ParseMode.MARKDOWN)
        return
    store.set_timezone(chat_id, context.args[0])
    user = store.get_user(chat_id)
    schedule_user(context.application, user)
    await update.message.reply_text(f"🌎 Zona horaria: *{user.tz}*", parse_mode=ParseMode.MARKDOWN)


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    store.ensure_user(chat_id)
    store.set_enabled(chat_id, False)
    schedule_user(context.application, store.get_user(chat_id))
    await update.message.reply_text("⏸️ Recordatorios pausados. Vuelve con /activar.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    store.ensure_user(chat_id)
    store.set_enabled(chat_id, True)
    user = store.get_user(chat_id)
    schedule_user(context.application, user)
    await update.message.reply_text(
        f"▶️ Recordatorios activos a las *{user.hour:02d}:{user.minute:02d}* ({user.tz}).",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    store.delete_user(chat_id)
    for job in context.application.job_queue.get_jobs_by_name(f"daily:{chat_id}"):
        job.schedule_removal()
    await update.message.reply_text("🗑️ Datos eliminados. Empieza de nuevo con /start.")


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    user = store.get_user(chat_id)
    if not user:
        await query.answer("Escribe /start primero")
        return
    day = today_for(user)

    if query.data == "sync":
        try:
            new_names, total, tiers = sync_badges(chat_id)
        except api.BuilderApiError as exc:
            await query.answer(f"API no disponible ({exc})", show_alert=True)
            return
        if new_names:
            await query.answer("¡Badge nueva! 🎉")
            await context.bot.send_message(
                chat_id, coach.congrats_message(new_names, total, tiers), parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.answer(f"Sigues en {total}/{cat.TOTAL}")
        return

    if query.data.startswith("done:"):
        task = query.data.split(":", 1)[1]
        if task in store.tasks_done(chat_id, day):
            store.remove_checkin(chat_id, day, task)
            await query.answer("Desmarcado")
        else:
            store.add_checkin(chat_id, day, task)
            streak = store.daily_streak(chat_id, task, day)
            if task in {"visit", "like", "comment"} and streak in (7, 30, 90):
                await query.answer(f"🔥 ¡{streak} días seguidos!", show_alert=True)
            else:
                await query.answer("¡Hecho! ✅")
        try:
            await query.edit_message_text(
                coach.daily_message(store, chat_id, day),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=routine_keyboard(chat_id, day),
            )
        except BadRequest:  # el mensaje puede no haber cambiado
            await query.edit_message_reply_markup(reply_markup=routine_keyboard(chat_id, day))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Error manejando update", exc_info=context.error)


async def post_init(app: Application) -> None:
    for user in store.all_users():
        schedule_user(app, user)
    log.info("Jobs programados para %d usuario(s)", len(store.all_users()))


def build_app(token: str) -> Application:
    app = Application.builder().token(token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler(["ayuda", "help"], cmd_help))
    app.add_handler(CommandHandler(["perfil", "profile", "alias"], cmd_profile))
    app.add_handler(CommandHandler("badges", cmd_badges))
    app.add_handler(CommandHandler(["hoy", "today", "mision"], cmd_today))
    app.add_handler(CommandHandler("sync", cmd_sync))
    app.add_handler(CommandHandler(["racha", "rachas"], cmd_streak))
    app.add_handler(CommandHandler("hora", cmd_time))
    app.add_handler(CommandHandler(["zona", "tz"], cmd_tz))
    app.add_handler(CommandHandler("pausar", cmd_pause))
    app.add_handler(CommandHandler("activar", cmd_resume))
    app.add_handler(CommandHandler("borrar", cmd_delete))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    return app


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN (ver .env.example)")
    build_app(token).run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
