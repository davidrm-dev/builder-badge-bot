"""El mensaje motivador de Bedrock: caché diaria, fallback y prompt."""

from __future__ import annotations

from datetime import date

import pytest

from bot import ai, coach
from bot.db import Store

DAY = date(2026, 3, 10)


@pytest.fixture()
def store(tmp_path) -> Store:
    return Store(tmp_path / "bot.db")


class FakeClient:
    """Imita `bedrock-runtime.converse` y cuenta las llamadas."""

    def __init__(self, text: str = "Vas 6 de 21, sigue así.", error: Exception | None = None):
        self.text = text
        self.error = error
        self.calls: list[dict] = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"output": {"message": {"content": [{"text": self.text}]}}}


@pytest.fixture()
def bedrock(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(ai, "MODEL_ID", "us.amazon.nova-lite-v1:0")
    monkeypatch.setattr("boto3.client", lambda *a, **k: client)
    return client


CTX = ai.Context(name="David", earned=6, total=21, streaks=[("Visita", 3, 7)], next_badge="Wish")


def test_sin_modelo_configurado_no_llama_a_bedrock(monkeypatch):
    monkeypatch.setattr(ai, "MODEL_ID", "")
    assert ai.generate("es", CTX) is None


def test_genera_mensaje_con_contexto_del_usuario(bedrock):
    assert ai.generate("es", CTX) == "Vas 6 de 21, sigue así."
    prompt = bedrock.calls[0]["messages"][0]["content"][0]["text"]
    assert "David" in prompt and "6 de 21" in prompt and "Visita: 3/7" in prompt
    assert "Wish" in prompt
    assert "español" in bedrock.calls[0]["system"][0]["text"]


def test_prompt_en_ingles_usa_el_system_en_ingles(bedrock):
    ai.generate("en", CTX)
    assert "English" in bedrock.calls[0]["system"][0]["text"]
    assert "6 of 21" in bedrock.calls[0]["messages"][0]["content"][0]["text"]


def test_sin_rachas_activas_lo_dice_explicito(bedrock):
    ai.generate("es", ai.Context(name=None, earned=21, total=21, streaks=[], next_badge=None))
    prompt = bedrock.calls[0]["messages"][0]["content"][0]["text"]
    assert "sin rachas activas" in prompt and "ninguna pendiente" in prompt


def test_respuesta_larga_se_recorta(monkeypatch, bedrock):
    bedrock.text = "x" * 1000
    assert len(ai.generate("es", CTX)) == ai.MAX_CHARS


def test_error_de_bedrock_devuelve_none(monkeypatch):
    monkeypatch.setattr(ai, "MODEL_ID", "modelo")
    monkeypatch.setattr("boto3.client", lambda *a, **k: FakeClient(error=RuntimeError("denied")))
    assert ai.generate("es", CTX) is None


def test_solo_llama_una_vez_al_dia_y_cachea(store, bedrock):
    store.ensure_user(1)
    assert ai.pep_talk(store, 1, "es", DAY, CTX) == "Vas 6 de 21, sigue así."
    bedrock.text = "otro mensaje"
    assert ai.pep_talk(store, 1, "es", DAY, CTX) == "Vas 6 de 21, sigue así."
    assert len(bedrock.calls) == 1
    assert ai.pep_talk(store, 1, "es", date(2026, 3, 11), CTX) == "otro mensaje"
    assert len(bedrock.calls) == 2


def test_la_cache_no_se_comparte_entre_usuarios(store, bedrock):
    store.ensure_user(1)
    store.ensure_user(2)
    ai.pep_talk(store, 1, "es", DAY, CTX)
    bedrock.text = "mensaje de otro"
    assert ai.pep_talk(store, 2, "es", DAY, CTX) == "mensaje de otro"


def test_fallo_de_bedrock_no_se_cachea(store, monkeypatch):
    monkeypatch.setattr(ai, "MODEL_ID", "modelo")
    monkeypatch.setattr("boto3.client", lambda *a, **k: FakeClient(error=RuntimeError("boom")))
    store.ensure_user(1)
    assert ai.pep_talk(store, 1, "es", DAY, CTX) is None
    assert store.get_pep_talk(1, DAY) is None


def test_coach_cae_al_mensaje_estatico_sin_bedrock(store, monkeypatch):
    monkeypatch.setattr(ai, "MODEL_ID", "")
    store.ensure_user(1)
    text = coach.pep_talk(store, 1, DAY, set(), "es")
    assert text and text in __import__("bot.i18n", fromlist=["MOTIVATION"]).MOTIVATION["es"]


def test_coach_usa_el_mensaje_de_bedrock_en_el_diario(store, bedrock):
    store.ensure_user(1)
    assert "Vas 6 de 21, sigue así." in coach.daily_message(store, 1, DAY, "es")


def test_contexto_del_coach_incluye_rachas_reales(store, bedrock):
    store.ensure_user(1)
    store.set_streak(1, "visit", 4, DAY)
    ctx = coach.ai_context(store, 1, DAY, set(), "es")
    assert ctx.earned == 0 and ctx.total == 21
    assert ("🔑 Sign-in", 4, 7) in ctx.streaks
    assert ctx.next_badge
