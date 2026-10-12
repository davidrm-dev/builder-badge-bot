"""Canal de correo: enlaces firmados, armado de correos (texto + HTML) y envío con Amazon SES.

Los correos no pueden recibir comandos, así que cada acción (confirmar, marcar un check-in,
ver ajustes, darse de baja) es un enlace a `bot.web` con un token firmado con HMAC: quien
tiene el enlace puede hacer esa acción para ese usuario y nada más.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import date

from . import badges as cat
from . import builder_api as api
from . import coach, core
from .config import email_from, link_secret
from .db import User
from .i18n import normalize, t

log = logging.getLogger("builder-badge-bot.email")

# --------------------------------------------------------------------------- enlaces firmados
DAY = 86400
# Vigencia de cada tipo de enlace en segundos; 0 = no vence (la baja siempre debe funcionar).
TTL = {"confirm": 2 * DAY, "checkin": 2 * DAY, "me": 90 * DAY, "unsub": 0}
PATHS = {"confirm": "confirm", "checkin": "c", "me": "me", "unsub": "u"}


class BadToken(Exception):
    pass


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(payload: str) -> bytes:
    return hmac.new(link_secret(), payload.encode(), hashlib.sha256).digest()[:16]


def sign(action: str, uid: int, extra: str = "", now: float | None = None) -> str:
    ttl = TTL[action]
    exp = int((now or time.time()) + ttl) if ttl else 0
    payload = f"{action}|{uid}|{extra}|{exp}"
    return f"{_b64(payload.encode())}.{_b64(_mac(payload))}"


def verify(token: str, action: str, now: float | None = None) -> tuple[int, str]:
    """Devuelve (uid, extra) si el token es de `action`, está bien firmado y no venció."""
    try:
        body, mac = token.split(".", 1)
        payload = _unb64(body).decode()
        got_action, uid, extra, exp = payload.split("|", 3)
        valid_mac = hmac.compare_digest(_unb64(mac), _mac(payload))
    except (ValueError, UnicodeDecodeError) as exc:
        raise BadToken(str(exc)) from exc
    if not valid_mac or got_action != action:
        raise BadToken("firma o acción inválida")
    if int(exp) and int(exp) < (now or time.time()):
        raise BadToken("vencido")
    return int(uid), extra


def url_for(base: str, action: str, uid: int, extra: str = "") -> str:
    return f"{base}/{PATHS[action]}?t={sign(action, uid, extra)}"


def checkin_extra(day: date, task: str) -> str:
    return f"{day.isoformat()}:{task}"


# --------------------------------------------------------------------------- markdown → correo
# Los textos de coach/i18n usan el Markdown de Telegram: *negrita*, _cursiva_, `código`.
_MD_HTML = (
    (re.compile(r"\*([^*\n]+)\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\w)_([^_\n]+)_(?!\w)"), r"<em>\1</em>"),
    (re.compile(r"`([^`\n]+)`"), r'<code style="font-family:monospace">\1</code>'),
)


def md_to_html(text: str) -> str:
    out = html.escape(text)
    for pattern, repl in _MD_HTML:
        out = pattern.sub(repl, out)
    return out.replace("\n", "<br>")


def md_to_text(text: str) -> str:
    out = text
    for pattern, _repl in _MD_HTML:
        out = pattern.sub(r"\1", out)
    return out


# --------------------------------------------------------------------------- armado de correos
@dataclass(frozen=True)
class Email:
    subject: str
    text: str
    html: str
    unsubscribe: str | None = None


def button(url: str, label: str, primary: bool = True) -> str:
    bg, fg = ("#232f3e", "#ffffff") if primary else ("#eef1f4", "#232f3e")
    return (
        f'<a href="{html.escape(url)}" style="display:inline-block;margin:4px 4px 4px 0;'
        f"padding:10px 14px;border-radius:8px;background:{bg};color:{fg};"
        f'text-decoration:none;font-weight:600">{html.escape(label)}</a>'
    )


def _layout(body_html: str, footer_html: str = "") -> str:
    footer = (
        f'<p style="margin-top:28px;font-size:12px;color:#6b7280">{footer_html}</p>' if footer_html else ""
    )
    return (
        '<!doctype html><html><body style="margin:0;padding:0;background:#f6f7f9">'
        '<div style="max-width:480px;margin:0 auto;padding:24px 16px;font-family:-apple-system,'
        'Segoe UI,Roboto,Helvetica,Arial,sans-serif;font-size:16px;line-height:1.5;color:#111827">'
        f"{body_html}{footer}</div></body></html>"
    )


def _footer(user: User, base: str, lang: str) -> tuple[str, str]:
    """(html, texto) del pie con enlaces a ajustes y baja."""
    me = url_for(base, "me", user.chat_id)
    unsub = url_for(base, "unsub", user.chat_id)
    note = t(lang, "email_footer", alias=user.alias or "")
    html_part = (
        f"{html.escape(note)}<br>"
        f'<a href="{html.escape(me)}" style="color:#6b7280">{html.escape(t(lang, "web_settings"))}</a> · '
        f'<a href="{html.escape(unsub)}" style="color:#6b7280">{html.escape(t(lang, "email_unsubscribe"))}</a>'
    )
    text_part = f"{note}\n{t(lang, 'web_settings')}: {me}\n{t(lang, 'email_unsubscribe')}: {unsub}"
    return html_part, text_part


def pending_tasks(store, user: User, day: date) -> list[tuple[str, str]]:
    """Tareas de la rutina que faltan hoy, como (task, etiqueta con icono)."""
    done = store.tasks_done(user.chat_id, day)
    earned = coach.earned_keys(store, user.chat_id)
    lang = normalize(user.lang)
    out = [
        (task, f"{icon} {t(lang, f'task_{task}')}")
        for task, icon, *_ in cat.DAILY_ROUTINE
        if task not in done
    ]
    out += [
        (task, f"{icon} {t(lang, f'task_{task}')}")
        for task, icon, *_ in cat.WEEKLY_ROUTINE
        if coach.weekly_pending(store, user.chat_id, task, day, earned)
    ]
    return out


def daily_email(
    store, user: User, base: str, day: date, new_names: list[str] | None = None, tiers: list[int] | None = None
) -> Email:
    lang = normalize(user.lang)
    total = store.badge_count(user.chat_id)
    blocks_md: list[str] = []
    if new_names:
        blocks_md.append(coach.congrats_message(new_names, total, tiers or [], lang))
    blocks_md.append(coach.daily_message(store, user.chat_id, day, lang))

    tasks = pending_tasks(store, user, day)
    links = [
        (label, url_for(base, "checkin", user.chat_id, checkin_extra(day, task))) for task, label in tasks
    ]
    me = url_for(base, "me", user.chat_id)
    footer_html, footer_text = _footer(user, base, lang)

    body = "".join(f"<p>{md_to_html(b)}</p>" for b in blocks_md)
    if links:
        body += f'<p style="margin-bottom:4px">{html.escape(t(lang, "email_checkin"))}</p>'
        body += "<p>" + "".join(button(url, f"✅ {label}") for label, url in links) + "</p>"
    body += "<p>" + button(cat.LINKS["home"], t(lang, "web_open_bc"), primary=False)
    body += button(me, t(lang, "email_btn_progress"), primary=False) + "</p>"

    text = "\n\n".join(md_to_text(b) for b in blocks_md)
    if links:
        text += f"\n\n{t(lang, 'email_checkin')}\n" + "\n".join(f"✅ {label}: {url}" for label, url in links)
    text += f"\n\n{t(lang, 'email_btn_progress')}: {me}\n\n{footer_text}"

    subject_key = "email_congrats_subject" if new_names else "email_daily_subject"
    return Email(
        subject=t(lang, subject_key, total=total, max=cat.TOTAL),
        text=text,
        html=_layout(body, footer_html),
        unsubscribe=url_for(base, "unsub", user.chat_id),
    )


def finished_email(user: User, base: str) -> Email:
    lang = normalize(user.lang)
    body_md = t(lang, "email_finished_body")
    footer_html, footer_text = _footer(user, base, lang)
    return Email(
        subject=t(lang, "email_finished_subject"),
        text=f"{md_to_text(body_md)}\n{cat.LINKS['rewards']}\n\n{footer_text}",
        html=_layout(
            f"<p>{md_to_html(body_md)}</p><p>{button(cat.LINKS['rewards'], t(lang, 'btn_rewards'))}</p>",
            footer_html,
        ),
        unsubscribe=url_for(base, "unsub", user.chat_id),
    )


def confirm_email(user: User, base: str) -> Email:
    lang = normalize(user.lang)
    url = url_for(base, "confirm", user.chat_id)
    body_md = t(lang, "email_confirm_body", name=user.name or user.alias or "", hour=core.hhmm(user), tz=user.tz)
    ignore = t(lang, "email_confirm_ignore")
    return Email(
        subject=t(lang, "email_confirm_subject"),
        text=f"{md_to_text(body_md)}\n\n{t(lang, 'email_confirm_btn')}: {url}\n\n{ignore}",
        html=_layout(
            f"<p>{md_to_html(body_md)}</p><p>{button(url, t(lang, 'email_confirm_btn'))}</p>",
            html.escape(ignore),
        ),
    )


def known_email(user: User, base: str) -> Email:
    lang = normalize(user.lang)
    url = url_for(base, "me", user.chat_id)
    body = t(lang, "email_known_body")
    return Email(
        subject=t(lang, "email_known_subject"),
        text=f"{body}\n{url}",
        html=_layout(f"<p>{html.escape(body)}</p><p>{button(url, t(lang, 'email_btn_progress'))}</p>"),
    )


# --------------------------------------------------------------------------- envío
_ses = None


def _client():
    global _ses
    if _ses is None:
        import boto3

        _ses = boto3.client("sesv2")
    return _ses


def send(to: str, email: Email) -> None:
    """Envía con SES. Si hay enlace de baja, agrega List-Unsubscribe de un clic (RFC 8058),
    que Gmail y Yahoo exigen a quien manda correos recurrentes."""
    simple: dict = {
        "Subject": {"Data": email.subject, "Charset": "UTF-8"},
        "Body": {
            "Text": {"Data": email.text, "Charset": "UTF-8"},
            "Html": {"Data": email.html, "Charset": "UTF-8"},
        },
    }
    if email.unsubscribe:
        simple["Headers"] = [
            {"Name": "List-Unsubscribe", "Value": f"<{email.unsubscribe}>"},
            {"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"},
        ]
    kwargs: dict = {
        "FromEmailAddress": email_from(),
        "Destination": {"ToAddresses": [to]},
        "Content": {"Simple": simple},
    }
    config_set = os.environ.get("SES_CONFIGURATION_SET")
    if config_set:
        kwargs["ConfigurationSetName"] = config_set
    _client().send_email(**kwargs)


def send_daily(store, user: User, base: str) -> None:
    """Sincroniza badges y manda la misión del día por correo (una sola pieza, con la
    felicitación arriba si hubo badge nueva)."""
    if not user.email:
        return
    try:
        new_names, total, tiers = core.sync_badges(store, user.chat_id)
    except api.BuilderApiError as exc:
        log.warning("sync falló para %s: %s", user.chat_id, exc)
        new_names, total, tiers = [], store.badge_count(user.chat_id), []
    if total >= cat.TOTAL:
        send(user.email, finished_email(user, base))
        store.set_enabled(user.chat_id, False)  # ya no hay misión que mandar
        return
    send(user.email, daily_email(store, user, base, core.today_for(user), new_names, tiers))
