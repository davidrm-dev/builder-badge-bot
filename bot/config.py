"""Carga del token: SSM Parameter Store en AWS, variable de entorno en local."""

from __future__ import annotations

import os

_cached: str | None = None


def telegram_token() -> str:
    global _cached
    if _cached:
        return _cached
    param = os.environ.get("TOKEN_PARAMETER")
    if param:
        import boto3

        ssm = boto3.client("ssm")
        _cached = ssm.get_parameter(Name=param, WithDecryption=True)["Parameter"]["Value"]
        return _cached
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Falta TELEGRAM_BOT_TOKEN o TOKEN_PARAMETER")
    _cached = token
    return _cached


def webhook_secret() -> str | None:
    return os.environ.get("WEBHOOK_SECRET")


def telegram_configured() -> bool:
    return bool(os.environ.get("TOKEN_PARAMETER") or os.environ.get("TELEGRAM_BOT_TOKEN"))


def link_secret() -> bytes:
    """Clave HMAC para firmar los enlaces de los correos (confirmar, check-in, baja)."""
    secret = os.environ.get("EMAIL_LINK_SECRET")
    if not secret:
        raise RuntimeError("Falta EMAIL_LINK_SECRET")
    return secret.encode()


def email_from() -> str:
    sender = os.environ.get("EMAIL_FROM")
    if not sender:
        raise RuntimeError("Falta EMAIL_FROM (ej. 'Builder Badge Coach <coach@tudominio.com>')")
    return sender


def public_base_url() -> str | None:
    """URL pública de las páginas web (Function URL o dominio propio), sin '/' final."""
    url = os.environ.get("PUBLIC_BASE_URL", "").strip()
    return url.rstrip("/") or None
