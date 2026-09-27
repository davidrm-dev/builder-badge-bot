"""API de la Mini App de Telegram.

La Mini App se abre dentro de Telegram y llama a estos endpoints con el `initData` que
firma Telegram con el token del bot, así que no hace falta login ni contraseñas: el
propio cliente de Telegram es la identidad.

Todas las respuestas devuelven el estado completo del usuario para que el frontend
simplemente vuelva a pintar la pantalla después de cada acción.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import badges as cat
from . import builder_api as api
from . import coach
from . import main as botmain
from .i18n import LANGS, normalize, t
from .main import hhmm, today_for

log = logging.getLogger("builder-badge-bot.miniapp")

INIT_DATA_MAX_AGE = 24 * 3600
_METRIC_ICON = {"visit": "🔑", "like": "❤️", "comment": "💬", "article_week": "📝", "wish_vote_week": "💡"}
DAILY_METRICS = ("visit", "like", "comment")
WEEKLY_METRICS = ("article_week", "wish_vote_week")
WEEKLY_TASKS = {task for task, *_ in cat.WEEKLY_ROUTINE}


class AuthError(Exception):
    """El initData no viene firmado por Telegram o ya venció."""


def parse_init_data(init_data: str, token: str, max_age: int = INIT_DATA_MAX_AGE) -> dict:
    """Valida la firma del `initData` de Telegram y devuelve el usuario que lo envió."""
    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received = fields.pop("hash", "")
    if not received:
        raise AuthError("initData sin hash")
    check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise AuthError("firma inválida")
    auth_date = int(fields.get("auth_date") or 0)
    if max_age and time.time() - auth_date > max_age:
        raise AuthError("initData vencido")
    user = json.loads(fields.get("user") or "{}")
    if not user.get("id"):
        raise AuthError("initData sin usuario")
    return user


# --------------------------------------------------------------------------- estado
def _badges_state(lang: str, earned: set[str]) -> list[dict]:
    return [
        {
            "key": b.key,
            "name": b.name,
            "phase": b.phase,
            "phase_name": cat.PHASE_NAMES[lang][b.phase],
            "how": b.how(lang),
            "url": b.url,
            "earned": b.key in earned,
        }
        for b in cat.CATALOG
    ]


def _routine_state(lang: str, done: set[str]) -> list[dict]:
    return [
        {
            "task": task,
            "icon": icon,
            "label": cat.routine_text(task, lang),
            "url": cat.LINKS[link],
            "done": task in done,
            "weekly": task in WEEKLY_TASKS,
        }
        for task, icon, _es, _en, link in cat.DAILY_ROUTINE + cat.WEEKLY_ROUTINE
    ]


def _streaks_state(chat_id: int, lang: str, earned: set[str], today) -> list[dict]:
    rows = []
    for metric in DAILY_METRICS + WEEKLY_METRICS:
        weekly = metric in WEEKLY_METRICS
        targets = [b for b in cat.CATALOG if b.metric == metric]
        pending = [b for b in targets if b.key not in earned and b.target]
        current = (
            botmain.store.weekly_streak(chat_id, metric, today)
            if weekly
            else botmain.store.daily_streak(chat_id, metric, today)
        )
        goal = min(b.target for b in pending) if pending else None
        rows.append(
            {
                "metric": metric,
                "icon": _METRIC_ICON[metric],
                "label": t(lang, f"metric_{metric}"),
                "streak": current,
                "goal": goal,
                "weekly": weekly,
                "adjustable": metric in DAILY_METRICS,
            }
        )
    return rows


def state(chat_id: int) -> dict:
    user = botmain.store.ensure_user(chat_id)
    lang = normalize(user.lang)
    today = today_for(user)
    earned = coach.earned_keys(botmain.store, chat_id)
    total = botmain.store.badge_count(chat_id)
    return {
        "lang": lang,
        "user": {
            "alias": user.alias,
            "name": user.name,
            "tz": user.tz,
            "time": hhmm(user),
            "hour": user.hour,
            "minute": user.minute,
            "enabled": user.enabled,
            "profile_url": cat.profile_url(user.alias) if user.alias else cat.LINKS["profile"],
        },
        "progress": {
            "earned": total,
            "total": cat.TOTAL,
            "percent": round(100 * total / cat.TOTAL),
            "tier": coach.tier_line(lang, total),
        },
        "badges": _badges_state(lang, earned),
        "routine": _routine_state(lang, botmain.store.tasks_done(chat_id, today)),
        "streaks": _streaks_state(chat_id, lang, earned, today),
        "next": [
            {"name": b.name, "how": b.how(lang), "url": b.url}
            for b in coach.next_targets(earned)
        ],
        "motivation": coach.motivation(lang),
        "links": cat.LINKS,
    }


# --------------------------------------------------------------------------- acciones
def _set_settings(chat_id: int, payload: dict) -> None:
    if "lang" in payload and payload["lang"] in LANGS:
        botmain.store.set_lang(chat_id, payload["lang"])
    if "tz" in payload:
        try:
            ZoneInfo(payload["tz"])
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("tz") from exc
        botmain.store.set_timezone(chat_id, payload["tz"])
    if "hour" in payload and "minute" in payload:
        hour, minute = int(payload["hour"]), int(payload["minute"])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("time")
        botmain.store.set_schedule(chat_id, hour, minute)
    if "enabled" in payload:
        botmain.store.set_enabled(chat_id, bool(payload["enabled"]))


def _set_profile(chat_id: int, alias: str) -> None:
    profile = api.get_profile(alias)
    botmain.store.set_profile(chat_id, profile.alias, profile.builder_profile_id, profile.name)
    botmain.sync_badges(chat_id, notify_new=False)


def _toggle_checkin(chat_id: int, payload: dict) -> None:
    task = payload.get("task")
    if task not in cat.ROUTINE_TEXT:
        raise ValueError("task")
    user = botmain.store.get_user(chat_id)
    today = today_for(user)
    if payload.get("done"):
        botmain.store.add_checkin(chat_id, today, task)
    else:
        botmain.store.remove_checkin(chat_id, today, task)


def _set_streak(chat_id: int, payload: dict) -> None:
    metric = payload.get("metric")
    if metric not in DAILY_METRICS:
        raise ValueError("metric")
    days = int(payload.get("days") or 0)
    max_target = max((b.target for b in cat.CATALOG if b.metric == metric and b.target), default=90)
    if not (0 <= days <= max_target):
        raise ValueError("days")
    user = botmain.store.get_user(chat_id)
    today = today_for(user)
    if days == 0:
        botmain.store.reset_streak(chat_id, metric, today)
    else:
        botmain.store.set_streak(chat_id, metric, days, today)


def handle(path: str, payload: dict, token: str) -> tuple[int, dict]:
    """Enruta una llamada de la Mini App. Devuelve (status, cuerpo JSON)."""
    try:
        tg_user = parse_init_data(payload.get("initData") or "", token)
    except (AuthError, ValueError) as exc:
        return 401, {"error": str(exc)}

    chat_id = int(tg_user["id"])
    is_new = botmain.store.get_user(chat_id) is None
    botmain.store.ensure_user(chat_id)
    if is_new and tg_user.get("language_code"):
        botmain.store.set_lang(chat_id, normalize(tg_user["language_code"].split("-")[0]))

    try:
        if path == "/api/state":
            pass
        elif path == "/api/settings":
            _set_settings(chat_id, payload)
        elif path == "/api/profile":
            _set_profile(chat_id, (payload.get("alias") or "").strip().lstrip("@"))
        elif path == "/api/checkin":
            _toggle_checkin(chat_id, payload)
        elif path == "/api/streak":
            _set_streak(chat_id, payload)
        elif path == "/api/sync":
            botmain.sync_badges(chat_id, notify_new=False)
        else:
            return 404, {"error": "not found"}
    except api.ProfileNotFound:
        return 404, {"error": "profile_not_found"}
    except api.BuilderApiError as exc:
        log.warning("API de Builder Center falló: %s", exc)
        return 502, {"error": "builder_api"}
    except (ValueError, TypeError) as exc:
        return 400, {"error": str(exc)}

    return 200, state(chat_id)
