"""Páginas web del canal de correo, servidas por una Lambda detrás de una Function URL.

    GET  /            formulario de inscripción
    POST /signup      valida alias y correo, manda el correo de confirmación
    GET  /confirm     activa al usuario (enlace firmado del correo)
    GET  /c, POST /c  marca un check-in (el GET solo muestra un botón: los filtros de correo
                      abren los enlaces para escanearlos y no deben marcar nada)
    GET  /me, POST /me  progreso y ajustes (hora, zona, idioma, pausa, borrar)
    GET  /u, POST /u  baja; el POST también sirve para List-Unsubscribe de un clic
"""

from __future__ import annotations

import base64
import html
import logging
import re
import time
from datetime import date, timedelta
from urllib.parse import parse_qs

from . import badges as cat
from . import builder_api as api
from . import coach, core
from . import email_channel as mail
from .config import public_base_url
from .db import User
from .i18n import LANG_NAMES, LANGS, normalize, t

log = logging.getLogger("builder-badge-bot.web")

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
TIME_RE = re.compile(r"([01]?\d|2[0-3]):([0-5]\d)")
# Mínimo entre correos de confirmación al mismo destino, para que el formulario no sirva
# para inundar el buzón de alguien.
CONFIRM_GAP_SECONDS = 600


# --------------------------------------------------------------------------- HTML
CSS = """
:root{--bg:#f6f7f9;--card:#fff;--fg:#111827;--muted:#6b7280;--line:#e5e7eb;--accent:#232f3e;--accent-fg:#fff;--soft:#eef1f4;--ok:#047857}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f1115;--card:#171a21;--fg:#e5e7eb;--muted:#9ca3af;--line:#2a2f3a;--accent:#ff9900;--accent-fg:#111;--soft:#232833;--ok:#34d399}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
main{max-width:520px;margin:0 auto;padding:24px 16px 48px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;margin:16px 0}
h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:0 0 12px}
p{margin:8px 0}.muted{color:var(--muted);font-size:14px}.ok{color:var(--ok)}
label{display:block;font-weight:600;margin:14px 0 4px}
input,select{width:100%;padding:10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);font:inherit}
input[type=checkbox]{width:auto;margin-right:8px}
.btn,button{display:inline-block;margin:6px 6px 0 0;padding:10px 14px;border-radius:8px;border:0;background:var(--accent);color:var(--accent-fg);font:inherit;font-weight:600;text-decoration:none;cursor:pointer}
.btn.soft,button.soft{background:var(--soft);color:var(--fg)}
button.danger{background:transparent;color:#b91c1c;border:1px solid currentColor}
code{font-family:ui-monospace,monospace}
.hp{position:absolute;left:-9999px}
"""


def page(lang: str, body: str, title: str = "Builder Badge Coach") -> str:
    return (
        f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex">'
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
        f"<body><main><h1>🏅 Builder Badge Coach</h1>{body}</main></body></html>"
    )


def card(inner: str) -> str:
    return f'<div class="card">{inner}</div>'


def link_btn(url: str, label: str, soft: bool = False) -> str:
    cls = "btn soft" if soft else "btn"
    return f'<a class="{cls}" href="{html.escape(url)}">{html.escape(label)}</a>'


def hidden(name: str, value: str) -> str:
    return f'<input type="hidden" name="{name}" value="{html.escape(value)}">'


def message_page(lang: str, text_md: str, extra: str = "") -> str:
    return page(lang, card(f"<p>{mail.md_to_html(text_md)}</p>{extra}"))


def invalid_link(lang: str) -> tuple[int, str]:
    return 400, message_page(lang, t(lang, "web_link_invalid"))


# --------------------------------------------------------------------------- inscripción
def signup_form(lang: str, values: dict[str, str] | None = None, error: str | None = None) -> str:
    v = values or {}
    err = f'<p style="color:#b91c1c">{html.escape(error)}</p>' if error else ""
    langs = "".join(
        f'<option value="{code}"{" selected" if code == lang else ""}>{LANG_NAMES[code]}</option>'
        for code in LANGS
    )
    form = f"""
<form method="post" action="signup">
  {err}
  <label for="email">{t(lang, "web_email")}</label>
  <input id="email" name="email" type="email" required autocomplete="email" value="{html.escape(v.get("email", ""))}">
  <label for="alias">{t(lang, "web_alias")}</label>
  <input id="alias" name="alias" required placeholder="davidrm" value="{html.escape(v.get("alias", ""))}">
  <p class="muted">{html.escape(t(lang, "web_alias_hint"))}</p>
  <label for="time">{t(lang, "web_time")}</label>
  <input id="time" name="time" type="time" required value="{html.escape(v.get("time", "08:00"))}">
  <label for="lang">{t(lang, "web_lang")}</label>
  <select id="lang" name="lang">{langs}</select>
  <input id="tz" name="tz" type="hidden" value="{html.escape(v.get("tz", core.DEFAULT_TZ))}">
  <input class="hp" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
  <button type="submit">{t(lang, "web_submit")}</button>
  <p class="muted">{html.escape(t(lang, "web_privacy"))}</p>
</form>
<script>try{{document.getElementById('tz').value=Intl.DateTimeFormat().resolvedOptions().timeZone||document.getElementById('tz').value}}catch(e){{}}</script>
"""
    return page(lang, f'<p class="muted">{html.escape(t(lang, "web_tagline"))}</p>' + card(form))


def do_signup(store, form: dict[str, str], base: str) -> tuple[int, str]:
    lang = normalize(form.get("lang"))
    email = form.get("email", "").strip().lower()
    alias = form.get("alias", "").strip().lstrip("@")
    if "builder.aws.com" in alias:
        alias = alias.rstrip("/").split("@")[-1].split("?")[0]
    if form.get("website"):  # honeypot: un bot llenó el campo oculto
        return 200, message_page(lang, t(lang, "web_check_inbox", email=email))
    if not EMAIL_RE.fullmatch(email) or len(email) > 254:
        return 400, signup_form(lang, form, t(lang, "web_err_email"))
    time_match = TIME_RE.fullmatch(form.get("time", ""))
    if not time_match:
        return 400, signup_form(lang, form, t(lang, "web_err_time"))
    try:
        profile = api.get_profile(alias)
    except api.ProfileNotFound:
        return 400, signup_form(lang, form, t(lang, "web_err_alias", alias=alias))
    except api.BuilderApiError as exc:
        return 503, signup_form(lang, form, t(lang, "api_down", error=exc))

    user, created = store.create_email_user(email, lang)
    if created:
        tz = form.get("tz", "")
        store.set_profile(user.chat_id, profile.alias, profile.builder_profile_id, profile.name)
        store.set_schedule(user.chat_id, int(time_match.group(1)), int(time_match.group(2)))
        store.set_enabled(user.chat_id, False)  # set_schedule activa; se activa al confirmar
        if core.valid_tz(tz):
            store.set_timezone(user.chat_id, tz)
        user = store.get_user(user.chat_id)
    # Si el correo ya existía no se toca nada: solo el dueño del buzón puede cambiar sus datos.
    last = store.last_confirm_sent(user.chat_id)
    if last is None or time.time() - last > CONFIRM_GAP_SECONDS:
        email_msg = mail.known_email(user, base) if user.enabled else mail.confirm_email(user, base)
        mail.send(email, email_msg)
        store.mark_confirm_sent(user.chat_id, time.time())
    # La respuesta es la misma exista o no el correo, para no revelar quién está inscrito.
    return 200, message_page(
        lang,
        t(lang, "web_check_inbox", email=email),
        f'<p class="muted">{html.escape(t(lang, "web_check_spam"))}</p>',
    )


def do_confirm(store, token: str, lang: str, base: str) -> tuple[int, str]:
    try:
        uid, _ = mail.verify(token, "confirm")
    except mail.BadToken:
        return invalid_link(lang)
    user = store.get_user(uid)
    if not user:
        return invalid_link(lang)
    store.set_enabled(uid, True)
    try:
        core.sync_badges(store, uid, notify_new=False)
    except api.BuilderApiError:
        pass
    lang = normalize(user.lang)
    text_md = t(lang, "web_confirmed", name=user.name or user.alias, hour=core.hhmm(user), tz=user.tz)
    return 200, message_page(
        lang, text_md, link_btn(mail.url_for(base, "me", uid), t(lang, "email_btn_progress"))
    )


# --------------------------------------------------------------------------- check-in
def checkin_prompt(token: str, lang: str) -> tuple[int, str]:
    """El GET no marca nada: muestra un formulario que el navegador envía solo.
    Los escáneres de enlaces de Outlook/Gmail no ejecutan JS, así que no generan check-ins."""
    form = (
        f'<form id="f" method="post" action="c">{hidden("t", token)}'
        f'<button type="submit">✅ {html.escape(t(lang, "web_checkin_btn"))}</button></form>'
        "<script>document.getElementById('f').submit()</script>"
    )
    return 200, page(lang, card(form))


def do_checkin(store, token: str, lang: str, base: str) -> tuple[int, str]:
    try:
        uid, extra = mail.verify(token, "checkin")
        day_s, task = extra.split(":", 1)
        day = date.fromisoformat(day_s)
    except (mail.BadToken, ValueError):
        return invalid_link(lang)
    user = store.get_user(uid)
    if not user or task not in cat.ROUTINE_TEXT:
        return invalid_link(lang)
    lang = normalize(user.lang)
    today = core.today_for(user)
    if day < today - timedelta(days=1):
        return 200, message_page(lang, t(lang, "web_checkin_old"), _today_buttons(store, user, base, today))
    store.add_checkin(uid, day, task)  # idempotente: abrir dos veces el enlace no cambia nada
    feedback = coach.streak_feedback(store, uid, task, day, lang)
    go = link_btn(cat.LINKS[cat.ROUTINE_LINK[task]], t(lang, "web_open_bc"))
    return 200, message_page(lang, feedback, f"<p>{go}</p>" + _today_buttons(store, user, base, today))


def _today_buttons(store, user: User, base: str, today: date) -> str:
    lang = normalize(user.lang)
    tasks = mail.pending_tasks(store, user, today)
    if not tasks:
        return f'<p class="ok">{html.escape(t(lang, "daily_routine_done"))}</p>'
    buttons = "".join(
        link_btn(mail.url_for(base, "checkin", user.chat_id, mail.checkin_extra(today, task)), f"✅ {label}", soft=True)
        for task, label in tasks
    )
    return f'<p class="muted">{html.escape(t(lang, "web_today_left"))}</p><p>{buttons}</p>'


# --------------------------------------------------------------------------- progreso y ajustes
def settings_page(store, user: User, token: str, base: str, notice: str = "") -> str:
    lang = normalize(user.lang)
    uid = user.chat_id
    today = core.today_for(user)
    earned = coach.earned_keys(store, uid)
    streaks = coach.streak_lines(store, uid, today, earned, lang)

    mission = card(
        f"<p>{mail.md_to_html(coach.daily_message(store, uid, today, lang))}</p>"
        + _today_buttons(store, user, base, today)
    )
    streak_card = (
        card(f"<h2>{mail.md_to_html(t(lang, 'streaks_title'))}</h2><p>{mail.md_to_html(chr(10).join(streaks))}</p>")
        if streaks
        else ""
    )
    board = card(f"<p>{mail.md_to_html(coach.badge_overview(store, uid, lang))}</p>")
    langs = "".join(
        f'<option value="{code}"{" selected" if code == lang else ""}>{LANG_NAMES[code]}</option>'
        for code in LANGS
    )
    checked = " checked" if user.enabled else ""
    settings = card(
        f"""<h2>{html.escape(t(lang, "web_settings"))}</h2>
<form method="post" action="me">{hidden("t", token)}{hidden("op", "save")}
  <label for="time">{t(lang, "web_time")}</label>
  <input id="time" name="time" type="time" required value="{core.hhmm(user)}">
  <label for="tz">{t(lang, "web_tz")}</label>
  <input id="tz" name="tz" required value="{html.escape(user.tz)}">
  <label for="lang">{t(lang, "web_lang")}</label>
  <select id="lang" name="lang">{langs}</select>
  <label><input type="checkbox" name="enabled" value="1"{checked}>{t(lang, "web_enabled")}</label>
  <button type="submit">{t(lang, "web_save")}</button>
</form>
<form method="post" action="me" onsubmit="return confirm({html.escape(repr(t(lang, "web_delete_confirm")))})">
  {hidden("t", token)}{hidden("op", "delete")}
  <button class="danger" type="submit">{t(lang, "web_delete")}</button>
</form>"""
    )
    note = f'<p class="ok">{html.escape(notice)}</p>' if notice else ""
    return page(lang, note + mission + streak_card + board + settings)


def do_me(store, method: str, token: str, form: dict[str, str], lang: str, base: str) -> tuple[int, str]:
    try:
        uid, _ = mail.verify(token, "me")
    except mail.BadToken:
        return invalid_link(lang)
    user = store.get_user(uid)
    if not user:
        return invalid_link(lang)
    notice = ""
    if method == "POST" and form.get("op") == "delete":
        store.delete_user(uid)
        return 200, message_page(normalize(user.lang), t(user.lang, "web_deleted"))
    if method == "POST" and form.get("op") == "save":
        time_match = TIME_RE.fullmatch(form.get("time", ""))
        if time_match:
            store.set_schedule(uid, int(time_match.group(1)), int(time_match.group(2)))
        if core.valid_tz(form.get("tz", "")):
            store.set_timezone(uid, form["tz"])
        store.set_lang(uid, normalize(form.get("lang")))
        store.set_enabled(uid, form.get("enabled") == "1")
        user = store.get_user(uid)
        notice = t(user.lang, "web_saved")
    return 200, settings_page(store, user, token, base, notice)


# --------------------------------------------------------------------------- baja
def do_unsubscribe(store, method: str, token: str, lang: str, base: str) -> tuple[int, str]:
    try:
        uid, _ = mail.verify(token, "unsub")
    except mail.BadToken:
        return invalid_link(lang)
    user = store.get_user(uid)
    if not user:
        return 200, message_page(lang, t(lang, "web_deleted"))
    lang = normalize(user.lang)
    if method == "POST":
        store.set_enabled(uid, False)
        return 200, message_page(
            lang,
            t(lang, "web_unsub_done"),
            link_btn(mail.url_for(base, "me", uid), t(lang, "web_settings"), soft=True),
        )
    form = (
        f"<h2>{html.escape(t(lang, 'web_unsub_title'))}</h2>"
        f'<form method="post" action="u">{hidden("t", token)}'
        f'<button type="submit">{html.escape(t(lang, "web_unsub_btn"))}</button></form>'
    )
    return 200, page(lang, card(form))


# --------------------------------------------------------------------------- router
def route(method: str, path: str, params: dict[str, str], headers: dict[str, str], base: str) -> tuple[int, str]:
    store = core.get_store()
    lang = normalize(params.get("lang") or _accept_lang(headers.get("accept-language", "")))
    token = params.get("t", "")
    path = "/" + path.strip("/")
    if path == "/" and method == "GET":
        return 200, signup_form(lang)
    if path == "/signup" and method == "POST":
        return do_signup(store, params, base)
    if path == "/confirm":
        return do_confirm(store, token, lang, base)
    if path == "/c":
        return do_checkin(store, token, lang, base) if method == "POST" else checkin_prompt(token, lang)
    if path == "/me":
        return do_me(store, method, token, params, lang, base)
    if path == "/u":
        return do_unsubscribe(store, method, token, lang, base)
    return 404, message_page(lang, "404")


def _accept_lang(header: str) -> str:
    first = header.split(",")[0].strip().lower()[:2]
    return first if first in LANGS else "en" if first else "es"


def _params(event: dict) -> dict[str, str]:
    params = {k: v[0] for k, v in parse_qs(event.get("rawQueryString") or "").items()}
    raw = event.get("body") or ""
    if raw:
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode()
        params.update({k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()})
    return params


def handler(event: dict, context: object) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    domain = event.get("requestContext", {}).get("domainName", "")
    base = public_base_url() or f"https://{domain}"
    try:
        status, body = route(method, event.get("rawPath") or "/", _params(event), headers, base)
    except Exception:
        log.exception("Error en %s %s", method, event.get("rawPath"))
        status, body = 500, page("es", card("<p>😵 Error. Intenta de nuevo en un rato.</p>"))
    return {
        "statusCode": status,
        "headers": {
            "content-type": "text/html; charset=utf-8",
            "cache-control": "no-store",
            "referrer-policy": "no-referrer",  # los tokens viajan en la URL
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
        },
        "body": body,
    }
