"""Aviso de privacidad: se sirve en los dos idiomas y queda enlazado desde formulario y correos."""

from __future__ import annotations

import pytest

from bot import core, privacy, web
from bot import email_channel as mail
from bot.db import Store

BASE = "https://coach.example"


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL_LINK_SECRET", "test-secret")
    s = Store(tmp_path / "p.sqlite3")
    monkeypatch.setattr(core, "_store", s)
    return s


@pytest.mark.parametrize(
    ("path", "heading", "lang_attr"),
    [("/privacidad", "Aviso de privacidad", 'lang="es"'), ("/privacy", "Privacy notice", 'lang="en"')],
)
def test_privacy_page_in_both_languages(store, path, heading, lang_attr):
    status, body = web.route("GET", path, {}, {}, BASE)
    assert status == 200
    assert heading in body and lang_attr in body
    assert "Bedrock" in body and "400" in body


def test_privacy_contact_only_when_configured(store, monkeypatch):
    assert "mailto:" not in web.route("GET", "/privacidad", {}, {}, BASE)[1]
    monkeypatch.setenv("PRIVACY_CONTACT", "hola@example.com")
    assert "mailto:hola@example.com" in web.route("GET", "/privacidad", {}, {}, BASE)[1]


def test_signup_form_links_privacy(store):
    assert 'href="/privacidad"' in web.signup_form("es")
    assert 'href="/privacy"' in web.signup_form("en")


def test_email_footer_links_privacy(store):
    user, _ = store.create_email_user("dev@example.com", "es")
    html_part, text_part = mail._footer(user, BASE, "es")
    assert privacy.url(BASE, "es") in html_part
    assert f"{BASE}/privacidad" in text_part
