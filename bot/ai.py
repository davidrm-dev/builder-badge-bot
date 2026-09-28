"""Mensaje motivador personalizado con Amazon Bedrock.

Se genera como mucho una vez al día por usuario (se cachea en el store), y ante cualquier
problema —modelo sin acceso, timeout, credenciales ausentes en local— se cae a los mensajes
estáticos de `coach`, así que el recordatorio diario nunca depende de que Bedrock responda.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("builder-badge-bot.ai")

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")
MAX_CHARS = 320

SYSTEM = {
    "es": (
        "Eres el entrenador de alguien que está completando las 21 insignias de AWS Builder "
        "Center. Escribe UN mensaje motivador de máximo dos frases, en español, cercano y "
        "concreto: menciona su racha o la insignia que tiene más cerca. Nada de listas, "
        "emojis al final como mucho uno, ni promesas de premios que no existen."
    ),
    "en": (
        "You coach someone working through the 21 AWS Builder Center badges. Write ONE "
        "motivating message, two sentences max, in English, warm and specific: mention their "
        "streak or the badge they are closest to. No lists, at most one emoji, and never "
        "promise rewards that don't exist."
    ),
}


@dataclass(frozen=True)
class Context:
    """Lo que el modelo necesita saber del usuario para el mensaje del día."""

    name: str | None
    earned: int
    total: int
    streaks: list[tuple[str, int, int | None]]  # (etiqueta, racha, meta)
    next_badge: str | None


def _prompt(lang: str, ctx: Context) -> str:
    streaks = ", ".join(
        f"{label}: {streak}/{goal}" if goal else f"{label}: {streak}"
        for label, streak, goal in ctx.streaks
    ) or ("sin rachas activas" if lang == "es" else "no active streaks")
    who = ctx.name or ("el builder" if lang == "es" else "the builder")
    target = ctx.next_badge or ("ninguna pendiente" if lang == "es" else "none pending")
    if lang == "es":
        return (
            f"Persona: {who}. Insignias: {ctx.earned} de {ctx.total}. "
            f"Rachas: {streaks}. Próxima insignia: {target}."
        )
    return (
        f"Person: {who}. Badges: {ctx.earned} of {ctx.total}. "
        f"Streaks: {streaks}. Next badge: {target}."
    )


def generate(lang: str, ctx: Context) -> str | None:
    """Pide el mensaje a Bedrock. Devuelve None si no hay modelo configurado o algo falla."""
    if not MODEL_ID:
        return None
    try:
        import boto3

        client = boto3.client("bedrock-runtime")
        resp = client.converse(
            modelId=MODEL_ID,
            system=[{"text": SYSTEM.get(lang, SYSTEM["es"])}],
            messages=[{"role": "user", "content": [{"text": _prompt(lang, ctx)}]}],
            inferenceConfig={"maxTokens": 200, "temperature": 0.8},
        )
        text = resp["output"]["message"]["content"][0]["text"].strip()
    except Exception:  # cualquier fallo de Bedrock cae al mensaje estático
        logger.exception("Bedrock no respondió, uso el mensaje estático")
        return None
    return text[:MAX_CHARS] or None


def pep_talk(store, chat_id: int, lang: str, day, ctx: Context) -> str | None:
    """Mensaje del día: reutiliza el cacheado y solo llama a Bedrock una vez por jornada."""
    cached = store.get_pep_talk(chat_id, day)
    if cached:
        return cached
    text = generate(lang, ctx)
    if text:
        store.save_pep_talk(chat_id, day, text)
    return text
