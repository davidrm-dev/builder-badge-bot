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
