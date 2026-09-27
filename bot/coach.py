"""Genera los mensajes del bot: progreso, misión del día, rachas y felicitaciones."""

from __future__ import annotations

import random
from datetime import date, timedelta

from . import badges as cat
from .db import Store
from .i18n import CHEERS, MOTIVATION, normalize, t


def motivation(lang: str) -> str:
    return random.choice(MOTIVATION[normalize(lang)])


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


def progress_line(lang: str, total: int) -> str:
    return t(lang, "progress", total=total, max=cat.TOTAL, bar=progress_bar(total, cat.TOTAL))


def tier_line(lang: str, total: int) -> str:
    lang = normalize(lang)
    remaining = [x for x in cat.TIER_VALUES if total < x]
    if not remaining:
        return t(lang, "tier_done")
    nxt = remaining[0]
    return t(lang, "tier_next", missing=nxt - total, reward=cat.REWARD_TIERS[lang][nxt])


def badge_overview(store: Store, chat_id: int, lang: str = "es") -> str:
    lang = normalize(lang)
    earned = earned_keys(store, chat_id)
    total_earned = store.badge_count(chat_id)
    lines = [t(lang, "overview_title"), progress_line(lang, total_earned), ""]
    for phase in sorted(cat.PHASE_NAMES[lang]):
        lines.append(cat.PHASE_NAMES[lang][phase])
        for badge in cat.CATALOG:
            if badge.phase != phase:
                continue
            mark = "✅" if badge.key in earned else "⬜"
            lines.append(f"{mark} {badge.name}")
        lines.append("")
    lines.append(tier_line(lang, total_earned))
    return "\n".join(lines).strip()


def streak_lines(store: Store, chat_id: int, today: date, earned: set[str], lang: str = "es") -> list[str]:
    lang = normalize(lang)
    lines = []
    for metric in ("visit", "like", "comment"):
        targets = [b for b in cat.CATALOG if b.metric == metric and b.key not in earned]
        if not targets:
            continue
        streak = store.daily_streak(chat_id, metric, today)
        goal = min(b.target for b in targets if b.target)
        lines.append(
            t(
                lang,
                "streak_days",
                label=t(lang, f"metric_{metric}"),
                streak=streak,
                goal=goal,
                missing=max(goal - streak, 0),
            )
        )
    for metric in ("article_week", "wish_vote_week"):
        targets = [b for b in cat.CATALOG if b.metric == metric and b.key not in earned]
        if not targets:
            continue
        weeks = store.weekly_streak(chat_id, metric, today)
        goal = min(b.target for b in targets if b.target)
        lines.append(
            t(
                lang,
                "streak_weeks",
                label=t(lang, f"metric_{metric}"),
                streak=weeks,
                goal=goal,
                missing=max(goal - weeks, 0),
            )
        )
    return lines


def daily_message(store: Store, chat_id: int, today: date, lang: str = "es") -> str:
    lang = normalize(lang)
    earned = earned_keys(store, chat_id)
    done = store.tasks_done(chat_id, today)
    total_earned = store.badge_count(chat_id)

    lines: list[str] = [t(lang, "daily_title"), progress_line(lang, total_earned), ""]

    lines.append(t(lang, "daily_routine"))
    for task, icon, _es, _en, _link in cat.DAILY_ROUTINE:
        mark = "✅" if task in done else "⬜"
        lines.append(f"{mark} {icon} {cat.routine_text(task, lang)}")
    lines.append("")

    targets = next_targets(earned)
    if targets:
        lines.append(t(lang, "daily_focus"))
        for badge in targets:
            lines.append(f"• *{badge.name}* — {badge.how(lang)}")
        lines.append("")

    weekly = [
        f"{icon} {cat.routine_text(task, lang)}"
        for task, icon, _es, _en, _link in cat.WEEKLY_ROUTINE
        if _weekly_pending(store, chat_id, task, today, earned)
    ]
    if weekly:
        lines.append(t(lang, "daily_weekly"))
        lines.extend(weekly)
        lines.append("")

    st = streak_lines(store, chat_id, today, earned, lang)
    if st:
        lines.append(t(lang, "daily_streaks"))
        lines.extend(st)
        lines.append("")

    lines.append(f"_{motivation(lang)}_")
    lines.append(t(lang, "daily_footer"))
    return "\n".join(lines)


_WEEKLY_BADGE = {"article_week": "article_4w", "wish_vote_week": "wish_vote_4w"}


def _weekly_pending(store: Store, chat_id: int, task: str, today: date, earned: set[str]) -> bool:
    if _WEEKLY_BADGE[task] in earned:
        return False
    return not _week_done(store, chat_id, task, today)


def _week_done(store: Store, chat_id: int, task: str, today: date) -> bool:
    monday = today - timedelta(days=today.weekday())
    days = store.days_with_task(chat_id, task)
    return any(monday <= d <= today for d in days)


def congrats_message(new_names: list[str], total: int, new_tiers: list[int], lang: str = "es") -> str:
    lang = normalize(lang)
    cheer = random.choice(CHEERS[lang])
    key = "congrats_title_plural" if len(new_names) > 1 else "congrats_title"
    lines = [t(lang, key, cheer=cheer)]
    lines.extend(f"🏅 {name}" for name in new_names)
    lines.append("")
    lines.append(progress_line(lang, total))
    for tier in new_tiers:
        lines.append("")
        lines.append(cat.REWARD_TIERS[lang][tier])
    lines.append("")
    lines.append(f"_{motivation(lang)}_")
    return "\n".join(lines)
