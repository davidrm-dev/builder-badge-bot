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
from .commands import register_commands
from .db import Store, User
from .i18n import LANG_NAMES, LANGS, normalize, t

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("builder-badge-bot")

DB_PATH = os.environ.get("BOT_DB_PATH", "data/bot.sqlite3")
DEFAULT_TZ = os.environ.get("BOT_DEFAULT_TZ", "America/Bogota")


def build_store():
    """DynamoDB si corre en Lambda (BOT_TABLE), SQLite en local/VM."""
    if os.environ.get("BOT_TABLE"):
        from .dynamo import DynamoStore

        return DynamoStore()
    return Store(DB_PATH)


store = build_store()


# --------------------------------------------------------------------------- utilidades
def user_tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.tz)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TZ)


def today_for(user: User) -> date:
    return datetime.now(user_tz(user)).date()


def lang_of(chat_id: int) -> str:
    user = store.get_user(chat_id)
    return normalize(user.lang if user else None)


def hhmm(user: User) -> str:
    return f"{user.hour:02d}:{user.minute:02d}"


def link_button(lang: str, key: str, link: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(t(lang, key), url=cat.LINKS[link])


def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(LANG_NAMES[code], callback_data=f"lang:{code}") for code in LANGS]]
    )


def routine_keyboard(chat_id: int, day: date, lang: str) -> InlineKeyboardMarkup:
    done = store.tasks_done(chat_id, day)
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for task, icon, _es, _en, _link in cat.DAILY_ROUTINE + cat.WEEKLY_ROUTINE:
        mark = "✅" if task in done else "⬜"
        row.append(
            InlineKeyboardButton(
                f"{mark} {icon} {t(lang, f'task_{task}')}", callback_data=f"done:{task}"
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([link_button(lang, "btn_open", "home"), link_button(lang, "btn_read", "learn")])
    rows.append([link_button(lang, "btn_write", "write"), link_button(lang, "btn_wishlist", "wishlist")])
    rows.append([
        InlineKeyboardButton(t(lang, "btn_sync"), callback_data="sync"),
        InlineKeyboardButton(t(lang, "btn_adv"), callback_data="adv"),
    ])
    return InlineKeyboardMarkup(rows)


# Métricas ajustables manualmente (rachas diarias únicamente)
_ADV_METRICS: tuple[tuple[str, str], ...] = (
    ("visit", "🔑"),
    ("like", "❤️"),
    ("comment", "💬"),
)


def adv_metric_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Teclado para seleccionar qué métrica ajustar."""
    rows = [
        [InlineKeyboardButton(
            f"{icon} {t(lang, f'metric_{metric}')}",
            callback_data=f"adv:{metric}"
        )]
        for metric, icon in _ADV_METRICS
    ]
    return InlineKeyboardMarkup(rows)


def adv_action_keyboard(lang: str, metric: str) -> InlineKeyboardMarkup:
    """Teclado de acciones para una métrica concreta."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "btn_adv_set"), callback_data=f"adv:set:{metric}"),
            InlineKeyboardButton(t(lang, "btn_adv_reset"), callback_data=f"adv:reset:{metric}"),
        ],
        [InlineKeyboardButton(t(lang, "btn_adv_back"), callback_data="adv")],
    ])


def board_keyboard(lang: str, alias: str | None) -> InlineKeyboardMarkup:
    profile = cat.profile_url(alias) if alias else cat.LINKS["profile"]
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(t(lang, "btn_profile"), url=profile),
                link_button(lang, "btn_rewards", "rewards"),
            ],
            [
                InlineKeyboardButton(t(lang, "btn_today"), callback_data="today"),
                InlineKeyboardButton(t(lang, "btn_sync"), callback_data="sync"),
            ],
        ]
    )


def welcome_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(t(lang, "btn_today"), callback_data="today"),
                link_button(lang, "btn_open", "home"),
            ]
        ]
    )


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
    tiers = store.pending_tiers(chat_id, total, list(cat.TIER_VALUES))
    if not notify_new:
        return [], total, []
    return new_names, total, tiers


# --------------------------------------------------------------------------- scheduling
def schedule_user(app: Application, user: User) -> None:
    if app.job_queue is None:  # en Lambda los recordatorios los dispara EventBridge
        return
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


async def send_daily(bot, chat_id: int) -> None:
    """Sincroniza badges y manda el recordatorio diario (usado por job_queue y por Lambda)."""
    user = store.get_user(chat_id)
    if not user or not user.enabled:
        return
    lang = normalize(user.lang)
    try:
        new_names, total, tiers = sync_badges(chat_id)
    except api.BuilderApiError as exc:
        log.warning("sync falló para %s: %s", chat_id, exc)
        new_names, total, tiers = [], store.badge_count(chat_id), []
    if new_names:
        await bot.send_message(
            chat_id,
            coach.congrats_message(new_names, total, tiers, lang),
            parse_mode=ParseMode.MARKDOWN,
        )
    day = today_for(user)
    if total >= cat.TOTAL:
        await bot.send_message(
            chat_id,
            t(lang, "finished"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[link_button(lang, "btn_rewards", "rewards")]]),
        )
        return
    await bot.send_message(
        chat_id,
        coach.daily_message(store, chat_id, day, lang),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=routine_keyboard(chat_id, day, lang),
    )


async def daily_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_daily(context.bot, context.job.chat_id)


# --------------------------------------------------------------------------- comandos
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    is_new = store.get_user(chat_id) is None
    store.ensure_user(chat_id)
    from_user = update.effective_user
    if is_new and from_user is not None and from_user.language_code:
        store.set_lang(chat_id, normalize(from_user.language_code.split("-")[0]))
        await update.message.reply_text(t("es", "choose_lang"), reply_markup=lang_keyboard())
    lang = lang_of(chat_id)
    await update.message.reply_text(
        t(lang, "welcome"), parse_mode=ParseMode.MARKDOWN, reply_markup=welcome_keyboard(lang)
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        t(lang_of(update.effective_chat.id), "help"), parse_mode=ParseMode.MARKDOWN
    )


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    store.ensure_user(chat_id)
    if context.args and context.args[0].lower() in LANGS:
        lang = context.args[0].lower()
        store.set_lang(chat_id, lang)
        await update.message.reply_text(t(lang, "lang_set"))
        return
    await update.message.reply_text(t("es", "choose_lang"), reply_markup=lang_keyboard())


async def set_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, alias: str) -> None:
    chat_id = update.effective_chat.id
    store.ensure_user(chat_id)
    lang = lang_of(chat_id)
    try:
        profile = api.get_profile(alias)
    except api.ProfileNotFound:
        await update.message.reply_text(
            t(lang, "profile_not_found", alias=alias), parse_mode=ParseMode.MARKDOWN
        )
        return
    except api.BuilderApiError as exc:
        await update.message.reply_text(t(lang, "api_down", error=exc))
        return
    store.set_profile(chat_id, profile.alias, profile.builder_profile_id, profile.name)
    first_time = store.badge_count(chat_id) == 0
    try:
        _new, total, _tiers = sync_badges(chat_id, notify_new=not first_time)
    except api.BuilderApiError:
        total = store.badge_count(chat_id)
    user = store.get_user(chat_id)
    schedule_user(context.application, user)
    targets = coach.next_targets(coach.earned_keys(store, chat_id), limit=1)
    hint = (
        t(lang, "next_hint", badge=targets[0].name, how=targets[0].how(lang))
        if targets
        else t(lang, "all_done_hint")
    )
    await update.message.reply_text(
        t(
            lang,
            "profile_ok",
            name=profile.name,
            alias=profile.alias,
            total=total,
            max=cat.TOTAL,
            bar=coach.progress_bar(total, cat.TOTAL),
            hour=hhmm(user),
            tz=user.tz,
            next_hint=hint,
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=board_keyboard(lang, profile.alias),
    )


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = lang_of(update.effective_chat.id)
    if not context.args:
        await update.message.reply_text(t(lang, "profile_usage"), parse_mode=ParseMode.MARKDOWN)
        return
    await set_profile(update, context, context.args[0].lstrip("@"))


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()

    # ---- Estado de conversación: esperando número de días para ajustar racha ----
    pending = getattr(context, "user_data", {}).get("pending_streak_set")
    if pending and pending.get("chat_id") == update.effective_chat.id:
        metric = pending["metric"]
        lang = lang_of(update.effective_chat.id)
        label = t(lang, f"metric_{metric}")
        user = store.get_user(update.effective_chat.id)
        today = today_for(user) if user else date.today()

        if not text.isdigit() or int(text) < 1:
            await update.message.reply_text(
                t(lang, "adv_set_invalid"), parse_mode=ParseMode.MARKDOWN
            )
            return  # Mantenemos el estado pendiente para reintentar

        days = int(text)
        # El máximo útil es el target más alto de esa métrica (90 días)
        max_target = max(
            (b.target for b in cat.CATALOG if b.metric == metric and b.target),
            default=90,
        )
        if days > max_target:
            await update.message.reply_text(
                t(lang, "adv_set_too_big", max=max_target), parse_mode=ParseMode.MARKDOWN
            )
            return  # También mantenemos estado, el usuario puede corregir

        store.set_streak(update.effective_chat.id, metric, days, today)
        if hasattr(context, "user_data"):
            context.user_data.pop("pending_streak_set", None)
        await update.message.reply_text(
            t(lang, "adv_set_ok", label=label, days=days), parse_mode=ParseMode.MARKDOWN
        )
        return
    # ---- Fin estado de conversación ----

    match = re.search(r"builder\.aws\.com/community/@([\w.\-]+)", text)
    if match:
        await set_profile(update, context, match.group(1))
        return
    if re.fullmatch(r"@?[\w.\-]{2,40}", text):
        await set_profile(update, context, text.lstrip("@"))
        return
    await update.message.reply_text(t(lang_of(update.effective_chat.id), "not_understood"))


def require_profile(update: Update) -> User | None:
    user = store.get_user(update.effective_chat.id)
    if not user or not user.bp_id:
        return None
    return user


async def ask_profile(update: Update) -> None:
    await update.message.reply_text(
        t(lang_of(update.effective_chat.id), "need_profile"), parse_mode=ParseMode.MARKDOWN
    )


async def cmd_badges(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = require_profile(update)
    if not user:
        await ask_profile(update)
        return
    try:
        sync_badges(user.chat_id, notify_new=False)
    except api.BuilderApiError:
        pass
    lang = normalize(user.lang)
    await update.message.reply_text(
        coach.badge_overview(store, user.chat_id, lang),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=board_keyboard(lang, user.alias),
    )


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = require_profile(update)
    if not user:
        await ask_profile(update)
        return
    day = today_for(user)
    lang = normalize(user.lang)
    await update.message.reply_text(
        coach.daily_message(store, user.chat_id, day, lang),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=routine_keyboard(user.chat_id, day, lang),
    )


async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = require_profile(update)
    if not user:
        await ask_profile(update)
        return
    lang = normalize(user.lang)
    try:
        new_names, total, tiers = sync_badges(user.chat_id)
    except api.BuilderApiError as exc:
        await update.message.reply_text(t(lang, "api_down", error=exc))
        return
    if new_names:
        await update.message.reply_text(
            coach.congrats_message(new_names, total, tiers, lang), parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            t(lang, "no_news", total=total, max=cat.TOTAL), parse_mode=ParseMode.MARKDOWN
        )


async def cmd_streak(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = require_profile(update)
    if not user:
        await ask_profile(update)
        return
    lang = normalize(user.lang)
    day = today_for(user)
    earned = coach.earned_keys(store, user.chat_id)
    lines = coach.streak_lines(store, user.chat_id, day, earned, lang)
    body = "\n".join(lines) if lines else t(lang, "streaks_none")
    await update.message.reply_text(
        f"{t(lang, 'streaks_title')}\n{body}\n\n{t(lang, 'streaks_hint')}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=routine_keyboard(user.chat_id, day, lang),
    )


async def cmd_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    store.ensure_user(chat_id)
    lang = lang_of(chat_id)
    if not context.args or not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", context.args[0]):
        await update.message.reply_text(t(lang, "time_usage"), parse_mode=ParseMode.MARKDOWN)
        return
    hour, minute = (int(x) for x in context.args[0].split(":"))
    store.set_schedule(chat_id, hour, minute)
    user = store.get_user(chat_id)
    schedule_user(context.application, user)
    await update.message.reply_text(
        t(lang, "time_set", hour=hhmm(user), tz=user.tz), parse_mode=ParseMode.MARKDOWN
    )


async def cmd_tz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    store.ensure_user(chat_id)
    lang = lang_of(chat_id)
    if not context.args:
        await update.message.reply_text(t(lang, "tz_usage"), parse_mode=ParseMode.MARKDOWN)
        return
    try:
        ZoneInfo(context.args[0])
    except (ZoneInfoNotFoundError, ValueError):
        await update.message.reply_text(t(lang, "tz_invalid"), parse_mode=ParseMode.MARKDOWN)
        return
    store.set_timezone(chat_id, context.args[0])
    user = store.get_user(chat_id)
    schedule_user(context.application, user)
    await update.message.reply_text(
        t(lang, "tz_set", tz=user.tz, hour=hhmm(user)), parse_mode=ParseMode.MARKDOWN
    )


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    store.ensure_user(chat_id)
    store.set_enabled(chat_id, False)
    schedule_user(context.application, store.get_user(chat_id))
    await update.message.reply_text(t(lang_of(chat_id), "paused"))


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    store.ensure_user(chat_id)
    store.set_enabled(chat_id, True)
    user = store.get_user(chat_id)
    schedule_user(context.application, user)
    await update.message.reply_text(
        t(normalize(user.lang), "resumed", hour=hhmm(user), tz=user.tz),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    lang = lang_of(chat_id)
    store.delete_user(chat_id)
    if context.application.job_queue is not None:
        for job in context.application.job_queue.get_jobs_by_name(f"daily:{chat_id}"):
            job.schedule_removal()
    await update.message.reply_text(t(lang, "deleted"))


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id

    if query.data.startswith("lang:"):
        lang = normalize(query.data.split(":", 1)[1])
        store.ensure_user(chat_id)
        store.set_lang(chat_id, lang)
        await query.answer(t(lang, "lang_set"))
        await context.bot.send_message(
            chat_id,
            t(lang, "welcome"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=welcome_keyboard(lang),
        )
        return

    user = store.get_user(chat_id)
    if not user:
        await query.answer(t("es", "cb_start_first"))
        return
    lang = normalize(user.lang)
    day = today_for(user)

    if query.data == "today":
        await query.answer()
        await context.bot.send_message(
            chat_id,
            coach.daily_message(store, chat_id, day, lang),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=routine_keyboard(chat_id, day, lang),
        )
        return

    if query.data == "sync":
        try:
            new_names, total, tiers = sync_badges(chat_id)
        except api.BuilderApiError as exc:
            await query.answer(t(lang, "api_down", error=exc), show_alert=True)
            return
        if new_names:
            await query.answer(t(lang, "cb_new_badge"))
            await context.bot.send_message(
                chat_id,
                coach.congrats_message(new_names, total, tiers, lang),
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await query.answer(t(lang, "cb_same", total=total, max=cat.TOTAL))
        return

    # ------------------------------------------------------------------ opciones avanzadas
    if query.data == "adv":
        # Menú principal de opciones avanzadas: selección de métrica
        await query.answer()
        earned = coach.earned_keys(store, chat_id)
        # Solo mostrar métricas que aún tienen badges pendientes
        pending_metrics = [
            (metric, icon) for metric, icon in _ADV_METRICS
            if any(b.metric == metric and b.key not in earned for b in cat.CATALOG)
        ]
        if not pending_metrics:
            await query.answer(t(lang, "streaks_none"), show_alert=True)
            return
        try:
            await query.edit_message_text(
                t(lang, "adv_title"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=adv_metric_keyboard(lang),
            )
        except BadRequest:
            pass
        return

    if query.data.startswith("adv:") and not query.data.startswith("adv:set:") and not query.data.startswith("adv:reset:"):
        # Pantalla de acción para una métrica concreta: muestra racha actual y opciones
        metric = query.data.split(":", 1)[1]
        valid_metrics = {m for m, _ in _ADV_METRICS}
        if metric not in valid_metrics:
            await query.answer()
            return
        await query.answer()
        streak = store.daily_streak(chat_id, metric, day)
        label = t(lang, f"metric_{metric}")
        try:
            await query.edit_message_text(
                t(lang, "adv_metric_title", label=label, streak=streak),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=adv_action_keyboard(lang, metric),
            )
        except BadRequest:
            pass
        return

    if query.data.startswith("adv:set:"):
        # El usuario quiere fijar el número de días: pedimos el número por chat
        metric = query.data.split(":", 2)[2]
        await query.answer()
        label = t(lang, f"metric_{metric}")
        # Guardamos el estado: esperamos un número de este usuario para esta métrica
        context.user_data["pending_streak_set"] = {"metric": metric, "chat_id": chat_id}
        await context.bot.send_message(
            chat_id,
            t(lang, "adv_set_prompt", label=label),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if query.data.startswith("adv:reset:"):
        # Reiniciar racha: borra sintéticos, arranca desde 0
        metric = query.data.split(":", 2)[2]
        await query.answer()
        store.reset_streak(chat_id, metric, day)
        label = t(lang, f"metric_{metric}")
        try:
            await query.edit_message_text(
                t(lang, "adv_reset_ok", label=label),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=adv_metric_keyboard(lang),
            )
        except BadRequest:
            await context.bot.send_message(
                chat_id,
                t(lang, "adv_reset_ok", label=label),
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    # ------------------------------------------------------------------ check-ins de rutina
    if query.data.startswith("done:"):
        task = query.data.split(":", 1)[1]
        if task in store.tasks_done(chat_id, day):
            store.remove_checkin(chat_id, day, task)
            await query.answer(t(lang, "cb_undone"))
        else:
            store.add_checkin(chat_id, day, task)
            # Mostrar siempre la racha actualizada para tareas con métrica de racha.
            # Para tareas sin racha (read) se muestra cb_done genérico.
            feedback = coach.streak_feedback(store, chat_id, task, day, lang)
            await query.answer(feedback, show_alert=bool(feedback != t(lang, "cb_done")))
        try:
            await query.edit_message_text(
                coach.daily_message(store, chat_id, day, lang),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=routine_keyboard(chat_id, day, lang),
            )
        except BadRequest:  # el mensaje puede no haber cambiado
            await query.edit_message_reply_markup(reply_markup=routine_keyboard(chat_id, day, lang))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Error manejando update", exc_info=context.error)


async def post_init(app: Application) -> None:
    await register_commands(app.bot)
    for user in store.all_users():
        schedule_user(app, user)
    log.info("Jobs programados para %d usuario(s)", len(store.all_users()))


def build_app(token: str, *, with_jobs: bool = True) -> Application:
    builder = Application.builder().token(token)
    if with_jobs:
        builder = builder.post_init(post_init)
    else:
        builder = builder.job_queue(None).updater(None)
    app = builder.build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler(["ayuda", "help"], cmd_help))
    app.add_handler(CommandHandler(["idioma", "language", "lang"], cmd_lang))
    app.add_handler(CommandHandler(["perfil", "profile", "alias"], cmd_profile))
    app.add_handler(CommandHandler("badges", cmd_badges))
    app.add_handler(CommandHandler(["hoy", "today", "mision"], cmd_today))
    app.add_handler(CommandHandler("sync", cmd_sync))
    app.add_handler(CommandHandler(["racha", "rachas", "streak"], cmd_streak))
    app.add_handler(CommandHandler(["hora", "time"], cmd_time))
    app.add_handler(CommandHandler(["zona", "timezone", "tz"], cmd_tz))
    app.add_handler(CommandHandler(["pausar", "pause"], cmd_pause))
    app.add_handler(CommandHandler(["activar", "resume"], cmd_resume))
    app.add_handler(CommandHandler(["borrar", "delete"], cmd_delete))
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
