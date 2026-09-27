"""Textos del bot en español e inglés. `t(lang, key, **kwargs)` devuelve el string ya formateado."""

from __future__ import annotations

LANGS = ("es", "en")
DEFAULT_LANG = "es"

LANG_NAMES = {"es": "🇪🇸 Español", "en": "🇬🇧 English"}

STRINGS: dict[str, dict[str, str]] = {
    "es": {
        "choose_lang": "🌐 Elige tu idioma / Choose your language:",
        "lang_set": "🇪🇸 Listo, te hablo en español. Cámbialo cuando quieras con /idioma.",
        "welcome": (
            "👋 *Soy tu coach para las 21 badges de AWS Builder Center.*\n\n"
            "Te digo cada día qué hacer, llevo tus rachas y te aviso apenas AWS te otorgue "
            "una badge nueva.\n\n"
            "*Empecemos en 2 pasos:*\n"
            "1️⃣ Mándame tu alias de Builder Center (o pega la URL de tu perfil).\n"
            "    Ejemplo: `/perfil davidrm`\n"
            "2️⃣ Elige a qué hora te escribo: `/hora 08:00`\n\n"
            "¿No sabes tu alias? Está en la URL de tu perfil: builder.aws.com/community/@*tualias*"
        ),
        "help": (
            "*🧭 Guía rápida*\n\n"
            "*Tu progreso*\n"
            "/badges – tablero con las 21 badges\n"
            "/hoy – misión de hoy con botones\n"
            "/racha – cómo van tus rachas\n"
            "/sync – pregunta a AWS si ya te dieron una badge nueva\n\n"
            "*Configuración*\n"
            "/perfil `alias` – conecta tu perfil (o pega la URL)\n"
            "/hora `HH:MM` – hora del recordatorio (ej. /hora 08:30)\n"
            "/zona `Area/Ciudad` – zona horaria (ej. /zona America/Bogota)\n"
            "/idioma – español o inglés\n"
            "/pausar · /activar – recordatorios off/on\n"
            "/borrar – elimina tus datos\n\n"
            "_AWS solo publica las badges ya ganadas, no el avance interno de cada racha. "
            "Por eso tú marcas los botones \"hecho\" y yo confirmo cada badge contra la API pública._"
        ),
        "need_profile": "Primero conecta tu perfil: `/perfil tualias` (o pégame la URL de tu perfil).",
        "profile_usage": "Mándame tu alias así: `/perfil davidrm`, o pega la URL de tu perfil.",
        "profile_not_found": (
            "No encontré el perfil `{alias}` 🤔\n"
            "Revisa el alias en la URL de tu perfil: builder.aws.com/community/@*tualias*"
        ),
        "api_down": "Builder Center no respondió ({error}). Intentemos de nuevo en un rato.",
        "profile_ok": (
            "✅ *Conectado:* {name} (@{alias})\n"
            "🏅 Badges detectadas: *{total}/{max}*  `{bar}`\n"
            "⏰ Te escribo a las *{hour}* ({tz})\n\n"
            "{next_hint}\n\n"
            "Mira tu tablero con /badges o arranca ya con /hoy."
        ),
        "next_hint": "🎯 Lo siguiente que te conviene atacar: *{badge}* — {how}",
        "all_done_hint": "🏆 ¡Ya las tienes todas!",
        "not_understood": (
            "No te entendí 🙃\n"
            "Mándame tu alias de Builder Center o usa /ayuda para ver los comandos."
        ),
        "time_usage": "Dime la hora en formato 24h: `/hora 08:30`",
        "time_set": "⏰ Listo, te escribo todos los días a las *{hour}* ({tz}).",
        "tz_usage": "Dime tu zona horaria: `/zona America/Bogota`",
        "tz_invalid": "Esa zona no existe 🤔 Usa el formato `Area/Ciudad`, por ejemplo `America/Bogota`.",
        "tz_set": "🌎 Zona horaria: *{tz}*. Tu recordatorio queda a las *{hour}*.",
        "paused": "⏸️ Recordatorios pausados. Cuando quieras volver: /activar.",
        "resumed": "▶️ Recordatorios activos a las *{hour}* ({tz}).",
        "deleted": "🗑️ Borré todos tus datos. Si quieres empezar de nuevo: /start.",
        "no_news": (
            "Sin novedades: sigues en *{total}/{max}*.\n"
            "Las badges pueden tardar unas horas en aparecer después de la acción. "
            "Sigue con la rutina de /hoy 💪"
        ),
        "streaks_title": "*🔥 Tus rachas*",
        "streaks_none": "Ya tienes todas las badges de racha. 🔥",
        "streaks_hint": "_Yo cuento lo que marcas en /hoy; AWS solo confirma la badge al final._",
        "daily_title": "☀️ *Misión del día · Builder Center*",
        "daily_routine": "*Rutina diaria · 10 min*",
        "daily_focus": "*🎯 Foco de hoy*",
        "daily_weekly": "*📅 Pendientes de la semana*",
        "daily_streaks": "*🔥 Rachas*",
        "daily_footer": "Marca lo que vayas haciendo 👇",
        "progress": "Progreso: *{total}/{max}*  `{bar}`",
        "tier_next": "Te faltan *{missing}* para: {reward}",
        "tier_done": "🏆 ¡Tienes las 21! Reclama tu recompensa en Builder Center.",
        "overview_title": "*🏅 Tus 21 badges*",
        "congrats_title": "🎉 *{cheer} Badge nueva:*",
        "congrats_title_plural": "🎉 *{cheer} Badges nuevas:*",
        "finished": (
            "🏆 *¡Completaste las 21 badges!*\n\n"
            "Esto no lo logra mucha gente: fueron meses de constancia. "
            "Reclama tu voucher en Builder Center y cuéntalo en un artículo, "
            "alguien más necesita leer cómo lo hiciste.\n\n"
            "Si ya no quieres recordatorios: /pausar"
        ),
        "btn_open": "🌐 Abrir Builder Center",
        "btn_read": "📖 Leer",
        "btn_write": "✍️ Escribir",
        "btn_wishlist": "💡 Wishlist",
        "btn_profile": "👤 Mi perfil",
        "btn_rewards": "🎁 Recompensas",
        "btn_settings": "⚙️ Editar perfil",
        "btn_sync": "🔄 Revisar badges",
        "btn_today": "☀️ Misión de hoy",
        "btn_go": "👉 Ir a {what}",
        "cb_done": "¡Hecho! ✅",
        "cb_undone": "Desmarcado",
        "cb_streak": "🔥 ¡{days} días seguidos!",
        "cb_start_first": "Escribe /start primero",
        "cb_new_badge": "¡Badge nueva! 🎉",
        "cb_same": "Sigues en {total}/{max}",
        "task_visit": "Sign-in",
        "task_read": "Leer",
        "task_like": "Like",
        "task_comment": "Comentar",
        "task_article_week": "Artículo semanal",
        "task_wish_vote_week": "Voto semanal",
        "metric_visit": "🔑 Sign-in",
        "metric_like": "❤️ Likes",
        "metric_comment": "💬 Comentarios",
        "metric_article_week": "📝 Artículos",
        "metric_wish_vote_week": "💡 Votos a wishes",
        "streak_days": "{label}: *{streak}/{goal}* días · faltan {missing}",
        "streak_weeks": "{label}: *{streak}/{goal}* semanas · faltan {missing}",
    },
    "en": {
        "choose_lang": "🌐 Choose your language / Elige tu idioma:",
        "lang_set": "🇬🇧 Done, I'll talk to you in English. Change it anytime with /language.",
        "welcome": (
            "👋 *I'm your coach for the 21 AWS Builder Center badges.*\n\n"
            "Every day I tell you exactly what to do, track your streaks, and ping you the "
            "moment AWS awards you a new badge.\n\n"
            "*Two steps to start:*\n"
            "1️⃣ Send me your Builder Center alias (or paste your profile URL).\n"
            "    Example: `/profile davidrm`\n"
            "2️⃣ Pick your reminder time: `/time 08:00`\n\n"
            "Don't know your alias? It's in your profile URL: builder.aws.com/community/@*youralias*"
        ),
        "help": (
            "*🧭 Quick guide*\n\n"
            "*Your progress*\n"
            "/badges – board with all 21 badges\n"
            "/today – today's mission with buttons\n"
            "/streak – how your streaks are going\n"
            "/sync – ask AWS whether a new badge landed\n\n"
            "*Settings*\n"
            "/profile `alias` – connect your profile (or paste the URL)\n"
            "/time `HH:MM` – reminder time (e.g. /time 08:30)\n"
            "/timezone `Area/City` – time zone (e.g. /timezone America/Bogota)\n"
            "/language – Spanish or English\n"
            "/pause · /resume – reminders off/on\n"
            "/delete – wipe your data\n\n"
            "_AWS only publishes badges you already earned, not the progress inside each streak. "
            "That's why you tap the \"done\" buttons and I confirm every badge against the public API._"
        ),
        "need_profile": "Connect your profile first: `/profile youralias` (or paste your profile URL).",
        "profile_usage": "Send me your alias like this: `/profile davidrm`, or paste your profile URL.",
        "profile_not_found": (
            "I couldn't find the profile `{alias}` 🤔\n"
            "Check the alias in your profile URL: builder.aws.com/community/@*youralias*"
        ),
        "api_down": "Builder Center didn't answer ({error}). Let's try again in a bit.",
        "profile_ok": (
            "✅ *Connected:* {name} (@{alias})\n"
            "🏅 Badges found: *{total}/{max}*  `{bar}`\n"
            "⏰ I'll message you at *{hour}* ({tz})\n\n"
            "{next_hint}\n\n"
            "Check your board with /badges or start right now with /today."
        ),
        "next_hint": "🎯 Best next move: *{badge}* — {how}",
        "all_done_hint": "🏆 You already have them all!",
        "not_understood": (
            "I didn't get that 🙃\n"
            "Send me your Builder Center alias or use /help to see the commands."
        ),
        "time_usage": "Give me the time in 24h format: `/time 08:30`",
        "time_set": "⏰ Done, I'll write to you every day at *{hour}* ({tz}).",
        "tz_usage": "Tell me your time zone: `/timezone America/Bogota`",
        "tz_invalid": "That zone doesn't exist 🤔 Use `Area/City`, for example `America/Bogota`.",
        "tz_set": "🌎 Time zone: *{tz}*. Your reminder is now at *{hour}*.",
        "paused": "⏸️ Reminders paused. Come back anytime with /resume.",
        "resumed": "▶️ Reminders on, at *{hour}* ({tz}).",
        "deleted": "🗑️ All your data is gone. Start again with /start whenever you want.",
        "no_news": (
            "Nothing new: still *{total}/{max}*.\n"
            "Badges can take a few hours to show up after the action. "
            "Keep the /today routine going 💪"
        ),
        "streaks_title": "*🔥 Your streaks*",
        "streaks_none": "You already have every streak badge. 🔥",
        "streaks_hint": "_I count what you tap in /today; AWS only confirms the badge at the end._",
        "daily_title": "☀️ *Today's mission · Builder Center*",
        "daily_routine": "*Daily routine · 10 min*",
        "daily_focus": "*🎯 Today's focus*",
        "daily_weekly": "*📅 This week*",
        "daily_streaks": "*🔥 Streaks*",
        "daily_footer": "Tap what you finish 👇",
        "progress": "Progress: *{total}/{max}*  `{bar}`",
        "tier_next": "*{missing}* to go for: {reward}",
        "tier_done": "🏆 All 21! Claim your reward in Builder Center.",
        "overview_title": "*🏅 Your 21 badges*",
        "congrats_title": "🎉 *{cheer} New badge:*",
        "congrats_title_plural": "🎉 *{cheer} New badges:*",
        "finished": (
            "🏆 *You completed all 21 badges!*\n\n"
            "Not many people get here: that was months of showing up. "
            "Claim your voucher in Builder Center and write an article about it, "
            "somebody out there needs to read how you did it.\n\n"
            "Done with reminders? /pause"
        ),
        "btn_open": "🌐 Open Builder Center",
        "btn_read": "📖 Read",
        "btn_write": "✍️ Write",
        "btn_wishlist": "💡 Wishlist",
        "btn_profile": "👤 My profile",
        "btn_rewards": "🎁 Rewards",
        "btn_settings": "⚙️ Edit profile",
        "btn_sync": "🔄 Check badges",
        "btn_today": "☀️ Today's mission",
        "btn_go": "👉 Go to {what}",
        "cb_done": "Done! ✅",
        "cb_undone": "Unmarked",
        "cb_streak": "🔥 {days} days in a row!",
        "cb_start_first": "Send /start first",
        "cb_new_badge": "New badge! 🎉",
        "cb_same": "Still {total}/{max}",
        "task_visit": "Sign-in",
        "task_read": "Read",
        "task_like": "Like",
        "task_comment": "Comment",
        "task_article_week": "Weekly article",
        "task_wish_vote_week": "Weekly vote",
        "metric_visit": "🔑 Sign-in",
        "metric_like": "❤️ Likes",
        "metric_comment": "💬 Comments",
        "metric_article_week": "📝 Articles",
        "metric_wish_vote_week": "💡 Wish votes",
        "streak_days": "{label}: *{streak}/{goal}* days · {missing} to go",
        "streak_weeks": "{label}: *{streak}/{goal}* weeks · {missing} to go",
    },
}

MOTIVATION = {
    "es": (
        "Cada día que apareces vale más que una semana de intención. 🚀",
        "La constancia es aburrida… hasta que llega el voucher. 💪",
        "10 minutos hoy > 2 horas el domingo. ⏱️",
        "Nadie recuerda el día que empezaste, todos ven el resultado. 🔥",
        "Tu yo de dentro de 90 días te está mirando. No lo defraudes. 👀",
        "Un comentario útil hoy puede ser la badge de mañana. 💬",
        "El algoritmo premia al que vuelve. Vuelve. 🔁",
        "No tienes que hacerlo perfecto, solo tienes que hacerlo hoy. ✅",
    ),
    "en": (
        "One day you show up beats a week of good intentions. 🚀",
        "Consistency is boring… until the voucher arrives. 💪",
        "10 minutes today > 2 hours on Sunday. ⏱️",
        "Nobody remembers the day you started, everybody sees the result. 🔥",
        "Your 90-days-from-now self is watching. Don't let them down. 👀",
        "A useful comment today can be tomorrow's badge. 💬",
        "The algorithm rewards whoever comes back. Come back. 🔁",
        "It doesn't have to be perfect, it just has to happen today. ✅",
    ),
}

CHEERS = {
    "es": ("¡Bien ahí!", "¡Esa es!", "¡Crack!", "¡Vamos con toda!", "¡Se siente bonito, no?"),
    "en": ("Nice one!", "That's it!", "Legend!", "Let's go!", "Feels good, right?"),
}


def normalize(lang: str | None) -> str:
    return lang if lang in LANGS else DEFAULT_LANG


def t(lang: str | None, key: str, **kwargs: object) -> str:
    lang = normalize(lang)
    text = STRINGS[lang].get(key) or STRINGS[DEFAULT_LANG][key]
    return text.format(**kwargs) if kwargs else text
