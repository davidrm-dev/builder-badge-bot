"""Genera el mensaje diario: progreso, misiones del día y mensajes motivadores."""

from __future__ import annotations

import random
from datetime import date

from . import badges as cat
from .db import Store

MOTIVATION = (
    "Cada día que apareces vale más que una semana de intención. 🚀",
    "La constancia es aburrida... hasta que llega el voucher. 💪",
    "10 minutos hoy > 2 horas el domingo. ⏱️",
    "Nadie recuerda el día que empezaste, todos ven el resultado. 🔥",
    "Tu yo de dentro de 90 días te está mirando. No lo defraudes. 👀",
    "Un comentario útil hoy puede ser la badge de mañana. 💬",
    "El algoritmo premia al que vuelve. Vuelve. 🔁",
)

CONGRATS = (
    "¡Bien ahí! 🎉",
    "¡Esa es! 🏅",
    "¡Crack! 🔥",
    "¡Vamos con toda! 🚀",
    "¡Se siente bonito, no? ✨",
)

TASK_LABEL = {
    "visit": "Sign-in",
    "read": "Leer",
    "like": "Like",
    "comment": "Comentar",
    "article_week": "Artículo semanal",
    "wish_vote_week": "Voto en wishes",
}


def progress_bar(done: int, total: int, width: int = 10) -> str:
    filled = round(width * done / total) if total else 0
    return "█" * filled + "░" * (width - filled)


def earned_keys(store: Store, chat_id: int) -> set[str]:
    return {k for k in store.known_badge_keys(chat_id) if k in cat.BY_KEY}


def pending_badges(earned: set[str]) -> list[cat.Badge]:
    return [b for b in cat.CATALOG if b.key not in earned]


def next_targets(earned: set[str], limit: int = 3) -> list[cat.Badge]:
    """Siguientes badges a atacar: primero las fases bajas, y de las rachas solo la más cercana."""
    picked: list[cat.Badge] = []
    seen_metrics: set[str] = set()
    for badge in sorted(pending_badges(earned), key=lambda b: b.phase):
        if badge.metric and badge.metric in seen_metrics:
            continue
        if badge.metric:
            seen_metrics.add(badge.metric)
        picked.append(badge)
        if len(picked) >= limit:
            break
    return picked


def badge_overview(store: Store, chat_id: int) -> str:
    earned = earned_keys(store, chat_id)
    total_earned = store.badge_count(chat_id)
    lines = [
        f"*Progreso: {total_earned}/{cat.TOTAL}*",
        f"`{progress_bar(total_earned, cat.TOTAL)}`",
        "",
    ]
    for phase in sorted(cat.PHASE_NAMES):
        lines.append(f"*{cat.PHASE_NAMES[phase]}*")
        for badge in cat.CATALOG:
            if badge.phase != phase:
                continue
            mark = "✅" if badge.key in earned else "⬜"
            lines.append(f"{mark} {badge.name}")
        lines.append("")
    remaining = [t for t in sorted(cat.REWARD_TIERS) if total_earned < t]
    if remaining:
        nxt = remaining[0]
        lines.append(f"Te faltan *{nxt - total_earned}* para: {cat.REWARD_TIERS[nxt]}")
    else:
        lines.append("🏆 ¡Tienes las 21! Reclama tu voucher en Student Rewards.")
    return "\n".join(lines).strip()


def streak_lines(store: Store, chat_id: int, today: date, earned: set[str]) -> list[str]:
    lines = []
    for metric, label in (("visit", "🔑 Sign-in"), ("like", "❤️ Likes"), ("comment", "💬 Comentarios")):
        targets = [b for b in cat.CATALOG if b.metric == metric and b.key not in earned]
        if not targets:
            continue
        streak = store.daily_streak(chat_id, metric, today)
        goal = min(b.target for b in targets if b.target)
        lines.append(f"{label}: {streak} día(s) seguidos → faltan {max(goal - streak, 0)} para {goal}")
    for metric, label in (("article_week", "📝 Artículos"), ("wish_vote_week", "💡 Votos a wishes")):
        targets = [b for b in cat.CATALOG if b.metric == metric and b.key not in earned]
        if not targets:
            continue
        weeks = store.weekly_streak(chat_id, metric, today)
        goal = min(b.target for b in targets if b.target)
        lines.append(f"{label}: {weeks} semana(s) seguidas → faltan {max(goal - weeks, 0)} para {goal}")
    return lines


def daily_message(store: Store, chat_id: int, today: date, greeting: str | None = None) -> str:
    earned = earned_keys(store, chat_id)
    done = store.tasks_done(chat_id, today)
    total_earned = store.badge_count(chat_id)

    lines: list[str] = []
    lines.append(greeting or "☀️ *Misión del día · Builder Center*")
    lines.append(f"Progreso: *{total_earned}/{cat.TOTAL}*  `{progress_bar(total_earned, cat.TOTAL)}`")
    lines.append("")

    lines.append("*Rutina diaria (10 min)*")
    for task, icon, text in cat.DAILY_ROUTINE:
        mark = "✅" if task in done else "⬜"
        lines.append(f"{mark} {icon} {text}")
    lines.append("")

    targets = next_targets(earned)
    if targets:
        lines.append("*Foco de hoy*")
        for badge in targets:
            lines.append(f"🎯 *{badge.name}* — {badge.how}")
        lines.append("")

    weekly = []
    if "article_4w" not in earned and not _week_done(store, chat_id, "article_week", today):
        weekly.append("📝 Publica el artículo de esta semana (racha de 4 semanas).")
    if "wish_vote_4w" not in earned and not _week_done(store, chat_id, "wish_vote_week", today):
        weekly.append("💡 Vota al menos un wish esta semana.")
    if weekly:
        lines.append("*Pendientes de la semana*")
        lines.extend(weekly)
        lines.append("")

    st = streak_lines(store, chat_id, today, earned)
    if st:
        lines.append("*Rachas*")
        lines.extend(st)
        lines.append("")

    lines.append(f"_{random.choice(MOTIVATION)}_")
    lines.append("Marca lo que vayas haciendo con los botones 👇")
    return "\n".join(lines)


def _week_done(store: Store, chat_id: int, task: str, today: date) -> bool:
    from datetime import timedelta

    monday = today - timedelta(days=today.weekday())
    days = store.days_with_task(chat_id, task)
    return any(monday <= d <= today for d in days)


def congrats_message(new_names: list[str], total: int, new_tiers: list[int]) -> str:
    lines = [f"🎉 *{random.choice(CONGRATS)} Badge{'s' if len(new_names) > 1 else ''} nueva{'s' if len(new_names) > 1 else ''}:*"]
    for name in new_names:
        lines.append(f"🏅 {name}")
    lines.append("")
    lines.append(f"Vas en *{total}/{cat.TOTAL}*  `{progress_bar(total, cat.TOTAL)}`")
    for tier in new_tiers:
        lines.append("")
        lines.append(cat.REWARD_TIERS[tier])
    lines.append("")
    lines.append(f"_{random.choice(MOTIVATION)}_")
    return "\n".join(lines)
