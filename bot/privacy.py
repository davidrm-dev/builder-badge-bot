"""Aviso de privacidad: una sola fuente para la página web y el resumen de Telegram.

Si cambias qué se guarda o con quién se comparte, actualiza este texto en el mismo commit.
"""

from __future__ import annotations

import html
import os

from .i18n import normalize

UPDATED = "2026-10-20"
PATHS = ("/privacidad", "/privacy")


def contact() -> str:
    return os.environ.get("PRIVACY_CONTACT", "").strip()


# Cada sección: (título, [párrafos]). Los párrafos admiten <strong> y <code>; nada más.
_SECTIONS = {
    "es": [
        (
            "Quién está detrás",
            [
                "Builder Badge Coach es un proyecto independiente y de código abierto (licencia MIT) "
                "que te ayuda a completar las badges de AWS Builder Center. "
                "<strong>No está afiliado a Amazon Web Services.</strong>",
            ],
        ),
        (
            "Qué datos guardo",
            [
                "<strong>Para identificarte:</strong> tu ID de chat de Telegram o tu correo "
                "(según el canal que uses).",
                "<strong>De Builder Center:</strong> tu alias, tu nombre público, tu ID de perfil y "
                "las badges que ya ganaste. Todo eso es información pública de tu perfil; "
                "nunca te pido contraseña ni inicio de sesión.",
                "<strong>Tus preferencias:</strong> hora del recordatorio, zona horaria, idioma y si "
                "está activo o en pausa.",
                "<strong>Tu progreso:</strong> los check-ins que marcas (visitar, leer, like, "
                "comentar…), los ajustes manuales de racha y qué hitos (7, 14, 21) ya te anuncié.",
                "<strong>Registros técnicos:</strong> cuando algo falla, el registro puede incluir tu "
                "ID de chat o tu correo para poder corregirlo.",
            ],
        ),
        (
            "Para qué los uso",
            [
                "Solo para mandarte la misión diaria, llevar tus rachas, avisarte de badges nuevas y "
                "mostrarte tu progreso. No hay publicidad, no vendo ni comparto tus datos con nadie "
                "para otros fines, y no hay rastreo de aperturas ni de clics en los correos.",
            ],
        ),
        (
            "Con quién se comparten",
            [
                "<strong>Amazon Web Services</strong> aloja el bot (Lambda, DynamoDB, SES, región "
                "us-east-1, Estados Unidos).",
                "<strong>Amazon Bedrock</strong> genera el mensaje motivador del día. Solo recibe tu "
                "nombre público, cuántas badges llevas, tus rachas y la siguiente badge; AWS indica "
                "que Bedrock no usa esos datos para entrenar modelos.",
                "<strong>Telegram</strong>, si usas ese canal, transporta los mensajes.",
                "<strong>AWS Builder Center</strong>: consulto su API pública con tu alias para leer "
                "tus badges.",
            ],
        ),
        (
            "Cuánto tiempo",
            [
                "Tu perfil y tus badges, mientras uses el bot. Los check-ins se borran solos a los "
                "400 días, el mensaje generado a los 7 días y los registros técnicos a los 30 días.",
            ],
        ),
        (
            "Tus opciones",
            [
                "<strong>Pausar:</strong> <code>/pausar</code> en Telegram, o el enlace de baja que "
                "trae cada correo.",
                "<strong>Borrar todo:</strong> <code>/borrar</code> en Telegram, o "
                "“Borrar mis datos” en la página de ajustes del correo. Se elimina tu perfil, "
                "tus badges, tus check-ins y tu correo de inmediato.",
                "<strong>Ver tus datos:</strong> <code>/badges</code> y <code>/racha</code> en "
                "Telegram, el panel de la Mini App o la página de progreso del correo.",
            ],
        ),
    ],
    "en": [
        (
            "Who runs this",
            [
                "Builder Badge Coach is an independent, open source project (MIT license) that "
                "helps you earn the AWS Builder Center badges. "
                "<strong>It is not affiliated with Amazon Web Services.</strong>",
            ],
        ),
        (
            "What I store",
            [
                "<strong>To identify you:</strong> your Telegram chat ID or your email address "
                "(depending on the channel you use).",
                "<strong>From Builder Center:</strong> your alias, public name, profile ID and the "
                "badges you've already earned. That's all public profile information; I never ask "
                "for a password or a login.",
                "<strong>Your preferences:</strong> reminder time, time zone, language and whether "
                "it's active or paused.",
                "<strong>Your progress:</strong> the check-ins you tap (visit, read, like, comment…), "
                "manual streak adjustments, and which milestones (7, 14, 21) I already announced.",
                "<strong>Technical logs:</strong> when something fails, the log may include your "
                "chat ID or email so it can be fixed.",
            ],
        ),
        (
            "What I use it for",
            [
                "Only to send your daily mission, track your streaks, tell you about new badges and "
                "show your progress. No ads, I don't sell or share your data for anything else, and "
                "there's no open or click tracking in the emails.",
            ],
        ),
        (
            "Who it's shared with",
            [
                "<strong>Amazon Web Services</strong> hosts the bot (Lambda, DynamoDB, SES, region "
                "us-east-1, United States).",
                "<strong>Amazon Bedrock</strong> writes the daily pep talk. It only receives your "
                "public name, badge count, streaks and next badge; AWS states that Bedrock doesn't "
                "use that data to train models.",
                "<strong>Telegram</strong> carries the messages if you use that channel.",
                "<strong>AWS Builder Center</strong>: I query its public API with your alias to read "
                "your badges.",
            ],
        ),
        (
            "How long",
            [
                "Your profile and badges, while you use the bot. Check-ins delete themselves after "
                "400 days, the generated message after 7 days and technical logs after 30 days.",
            ],
        ),
        (
            "Your choices",
            [
                "<strong>Pause:</strong> <code>/pause</code> on Telegram, or the unsubscribe link in "
                "every email.",
                "<strong>Delete everything:</strong> <code>/delete</code> on Telegram, or "
                "“Delete my data” on the email settings page. Your profile, badges, check-ins and "
                "email are removed right away.",
                "<strong>See your data:</strong> <code>/badges</code> and <code>/streak</code> on "
                "Telegram, the Mini App panel, or the email progress page.",
            ],
        ),
    ],
}

_TITLE = {"es": "Aviso de privacidad", "en": "Privacy notice"}
_UPDATED = {"es": "Última actualización", "en": "Last updated"}
_CONTACT = {"es": "Contacto", "en": "Contact"}
_SUMMARY = {
    "es": (
        "🔒 *Privacidad*\n"
        "Guardo lo mínimo: tu ID de chat, tu alias y tus badges públicas de Builder Center, "
        "tu horario y tus check-ins. Sin publicidad ni rastreo. "
        "Con /pausar dejo de escribirte y con /borrar elimino todo."
    ),
    "en": (
        "🔒 *Privacy*\n"
        "I store the minimum: your chat ID, your Builder Center alias and public badges, "
        "your schedule and your check-ins. No ads, no tracking. "
        "/pause stops the messages and /delete removes everything."
    ),
}


def title(lang: str) -> str:
    return _TITLE[normalize(lang)]


def body_html(lang: str) -> str:
    lang = normalize(lang)
    parts = [f"<h2>{html.escape(_TITLE[lang])}</h2>"]
    parts.append(f'<p class="muted">{_UPDATED[lang]}: {UPDATED}</p>')
    for heading, paragraphs in _SECTIONS[lang]:
        parts.append(f"<h3>{html.escape(heading)}</h3>")
        parts.extend(f"<p>{p}</p>" for p in paragraphs)
    if contact():
        mail = html.escape(contact())
        parts.append(f"<h3>{_CONTACT[lang]}</h3><p><a href=\"mailto:{mail}\">{mail}</a></p>")
    return "".join(parts)


def summary(lang: str) -> str:
    return _SUMMARY[normalize(lang)]


def url(base: str, lang: str) -> str:
    return f"{base.rstrip('/')}{PATHS[0] if normalize(lang) == 'es' else PATHS[1]}"
