"""API de la Mini App: firma de Telegram, estado y acciones."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from bot import builder_api as api
from bot import lambda_webhook, main as botmain, miniapp
from bot.db import Store

TOKEN = "123456:TEST-TOKEN"
CHAT_ID = 4242


def init_data(token: str = TOKEN, chat_id: int = CHAT_ID, auth_date: int | None = None) -> str:
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAA",
        "user": json.dumps({"id": chat_id, "first_name": "David", "language_code": "es"}),
    }
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    botmain.store = Store(tmp_path / "miniapp.sqlite3")
    monkeypatch.setattr(
        api, "get_profile",
        lambda alias: api.Profile(alias="davidrm", builder_profile_id="bp-1", name="David"),
    )
    monkeypatch.setattr(
        api, "get_awarded_badges",
        lambda bp_id: [
            api.AwardedBadge(
                badge_id="activity_badge.profile.about",
                display_name="Hello, World!",
                description="",
                category="Getting Started",
                awarded_epoch=1.79e9,
            )
        ],
    )
    return botmain.store


def call(path: str, **payload):
    return miniapp.handle(path, {"initData": init_data(), **payload}, TOKEN)


# --------------------------------------------------------------------------- firma
def test_init_data_valido_devuelve_al_usuario():
    assert miniapp.parse_init_data(init_data(), TOKEN)["id"] == CHAT_ID


@pytest.mark.parametrize(
    "data",
    [
        init_data(token="999:OTRO-TOKEN"),  # firmado con otro bot
        init_data()[:-4] + "0000",  # hash alterado
        "user=%7B%22id%22%3A1%7D",  # sin hash
    ],
)
def test_init_data_invalido_es_rechazado(data):
    with pytest.raises(miniapp.AuthError):
        miniapp.parse_init_data(data, TOKEN)


def test_init_data_vencido_es_rechazado():
    viejo = init_data(auth_date=int(time.time()) - 2 * miniapp.INIT_DATA_MAX_AGE)
    with pytest.raises(miniapp.AuthError):
        miniapp.parse_init_data(viejo, TOKEN)


def test_api_sin_firma_responde_401(env):
    status, body = miniapp.handle("/api/state", {"initData": "user=%7B%22id%22%3A1%7D"}, TOKEN)
    assert status == 401 and "error" in body


# --------------------------------------------------------------------------- estado y acciones
def test_state_trae_catalogo_rutina_y_rachas(env):
    status, body = call("/api/state")
    assert status == 200
    assert len(body["badges"]) == body["progress"]["total"] == 21
    assert {r["task"] for r in body["routine"]} == {
        "visit", "read", "like", "comment", "article_week", "wish_vote_week"
    }
    assert {s["metric"] for s in body["streaks"]} == {
        "visit", "like", "comment", "article_week", "wish_vote_week"
    }


def test_conectar_perfil_sincroniza_badges(env):
    status, body = call("/api/profile", alias="@davidrm")
    assert status == 200
    assert body["user"]["alias"] == "davidrm"
    assert body["progress"]["earned"] == 1
    assert next(b for b in body["badges"] if b["key"] == "hello_world")["earned"]


def test_perfil_inexistente_responde_404(env, monkeypatch):
    monkeypatch.setattr(api, "get_profile", lambda alias: (_ for _ in ()).throw(api.ProfileNotFound(alias)))
    status, body = call("/api/profile", alias="nadie")
    assert status == 404 and body["error"] == "profile_not_found"


def test_checkin_marca_y_desmarca(env):
    _status, body = call("/api/checkin", task="visit", done=True)
    assert next(r for r in body["routine"] if r["task"] == "visit")["done"]
    _status, body = call("/api/checkin", task="visit", done=False)
    assert not next(r for r in body["routine"] if r["task"] == "visit")["done"]


def test_ajuste_de_racha_y_reinicio(env):
    _status, body = call("/api/streak", metric="visit", days=5)
    assert next(s for s in body["streaks"] if s["metric"] == "visit")["streak"] == 5
    _status, body = call("/api/streak", metric="visit", days=0)
    assert next(s for s in body["streaks"] if s["metric"] == "visit")["streak"] == 0


def test_ajustes_guardan_hora_zona_idioma_y_pausa(env):
    _status, body = call("/api/settings", hour=7, minute=15)
    assert body["user"]["time"] == "07:15"
    _status, body = call("/api/settings", tz="America/Mexico_City")
    assert body["user"]["tz"] == "America/Mexico_City"
    _status, body = call("/api/settings", lang="en")
    assert body["lang"] == "en"
    _status, body = call("/api/settings", enabled=False)
    assert body["user"]["enabled"] is False


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/settings", {"hour": 99, "minute": 0}),
        ("/api/settings", {"tz": "Marte/Olympus"}),
        ("/api/streak", {"metric": "inventada", "days": 3}),
        ("/api/streak", {"metric": "visit", "days": 5000}),
        ("/api/checkin", {"task": "inventada", "done": True}),
    ],
)
def test_datos_invalidos_responden_400(env, path, payload):
    status, _body = call(path, **payload)
    assert status == 400


def test_ruta_desconocida_responde_404(env):
    status, _body = call("/api/loquesea")
    assert status == 404


# --------------------------------------------------------------------------- enrutado de la Lambda
def _event(method: str, path: str, body: str = "{}") -> dict:
    return {
        "requestContext": {"http": {"method": method, "path": path}},
        "headers": {},
        "body": body,
    }


def test_get_sirve_el_html_de_la_miniapp(env, monkeypatch):
    monkeypatch.setattr(lambda_webhook, "telegram_token", lambda: TOKEN)
    res = lambda_webhook.handler(_event("GET", "/"), None)
    assert res["statusCode"] == 200
    assert res["headers"]["content-type"].startswith("text/html")
    assert "telegram-web-app.js" in res["body"]


def test_post_api_pasa_por_la_miniapp(env, monkeypatch):
    monkeypatch.setattr(lambda_webhook, "telegram_token", lambda: TOKEN)
    res = lambda_webhook.handler(
        _event("POST", "/api/state", json.dumps({"initData": init_data()})), None
    )
    assert res["statusCode"] == 200
    assert json.loads(res["body"])["progress"]["total"] == 21
