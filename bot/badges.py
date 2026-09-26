"""Catálogo de las 21 badges de AWS Builder Center y consejos para conseguirlas."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Badge:
    key: str
    name: str
    phase: int
    metric: str | None  # visit | like | comment | article | wish | None
    target: int | None  # días/semanas de racha necesarios
    how: str
    api_ids: tuple[str, ...] = ()
    aliases: tuple[str, ...] = field(default=())


CATALOG: tuple[Badge, ...] = (
    Badge(
        key="hello_world",
        name="Hello, World!",
        phase=1,
        metric=None,
        target=None,
        how="Completa la sección About de tu perfil (bio, ubicación, redes).",
        api_ids=("activity_badge.profile.about",),
    ),
    Badge(
        key="photo_finisher",
        name="Photo Finisher",
        phase=1,
        metric=None,
        target=None,
        how="Sube una foto de perfil y guarda los cambios.",
        api_ids=("activity_badge.profile.photo",),
    ),
    Badge(
        key="knowledge_seeker",
        name="Knowledge Seeker",
        phase=1,
        metric=None,
        target=None,
        how="Lee 10 artículos distintos (elige temas que estés estudiando: Lambda, S3, Bedrock...).",
        api_ids=("activity_badge.article.10read",),
    ),
    Badge(
        key="discussion_debut",
        name="Discussion Debut",
        phase=1,
        metric=None,
        target=None,
        how="Deja tu primer comentario en un artículo o discusión.",
        api_ids=("activity_badge.comment.first",),
    ),
    Badge(
        key="first_article",
        name="First Article",
        phase=1,
        metric=None,
        target=None,
        how="Publica tu primer artículo: algo que aprendiste, construiste o resolviste.",
        api_ids=("activity_badge.article.first",),
    ),
    Badge(
        key="first_wish",
        name="First Wish",
        phase=1,
        metric=None,
        target=None,
        how="Publica tu primer Wish en AWS Wishlist (busca antes para no duplicar ideas).",
        api_ids=("activity_badge.wish.first",),
    ),
    Badge(
        key="visit_7",
        name="7-Day Visit Streak",
        phase=2,
        metric="visit",
        target=7,
        how="Inicia sesión en Builder Center 7 días seguidos.",
        api_ids=("activity_badge.visitor.streak.7day",),
    ),
    Badge(
        key="like_7",
        name="7-Day Like Streak",
        phase=2,
        metric="like",
        target=7,
        how="Dale like a contenido útil todos los días durante 7 días seguidos.",
        api_ids=("activity_badge.like.streak.7day",),
    ),
    Badge(
        key="comment_7",
        name="7-Day Comment Streak",
        phase=2,
        metric="comment",
        target=7,
        how="Comenta algo con sustancia todos los días durante 7 días seguidos.",
        api_ids=("activity_badge.comment.streak.7day",),
    ),
    Badge(
        key="wish_vote_4w",
        name="4-Week Wish Vote Streak",
        phase=2,
        metric="wish_vote_week",
        target=4,
        how="Vota wishes al menos una vez por semana, 4 semanas seguidas.",
        api_ids=("activity_badge.wishvote.streak.4week", "activity_badge.wish.vote.streak.4week"),
    ),
    Badge(
        key="article_4w",
        name="4-Week Article Publishing Streak",
        phase=2,
        metric="article_week",
        target=4,
        how="Publica un artículo por semana durante 4 semanas seguidas.",
        api_ids=("activity_badge.article.streak.4week",),
    ),
    Badge(
        key="visit_30",
        name="30-Day Visit Streak",
        phase=3,
        metric="visit",
        target=30,
        how="Mantén el sign-in diario hasta 30 días seguidos.",
        api_ids=("activity_badge.visitor.streak.30day",),
    ),
    Badge(
        key="like_30",
        name="30-Day Like Streak",
        phase=3,
        metric="like",
        target=30,
        how="Mantén el like diario hasta 30 días seguidos.",
        api_ids=("activity_badge.like.streak.30day",),
    ),
    Badge(
        key="comment_30",
        name="30-Day Comment Streak",
        phase=3,
        metric="comment",
        target=30,
        how="Mantén el comentario diario hasta 30 días seguidos.",
        api_ids=("activity_badge.comment.streak.30day",),
    ),
    Badge(
        key="visit_90",
        name="90-Day Visit Streak",
        phase=4,
        metric="visit",
        target=90,
        how="Sign-in diario durante 90 días seguidos (empieza ya, es la más larga).",
        api_ids=("activity_badge.visitor.streak.90day",),
    ),
    Badge(
        key="like_90",
        name="90-Day Like Streak",
        phase=4,
        metric="like",
        target=90,
        how="Like diario durante 90 días seguidos.",
        api_ids=("activity_badge.like.streak.90day",),
    ),
    Badge(
        key="comment_90",
        name="90-Day Comment Streak",
        phase=4,
        metric="comment",
        target=90,
        how="Comentario diario durante 90 días seguidos.",
        api_ids=("activity_badge.comment.streak.90day",),
    ),
    Badge(
        key="conversation_starter",
        name="Conversation Starter",
        phase=5,
        metric=None,
        target=None,
        how="Consigue respuestas en 10 de tus comentarios: haz preguntas abiertas al final de cada comentario.",
        api_ids=("activity_badge.comment.reply.10",),
    ),
    Badge(
        key="meaningful_contributor",
        name="Meaningful Contributor",
        phase=5,
        metric=None,
        target=None,
        how="Consigue 10 likes en 5 comentarios distintos: aporta datos, experiencia o un tip concreto.",
        api_ids=("activity_badge.comment.like.10x5",),
    ),
    Badge(
        key="valued_creator",
        name="Valued Creator",
        phase=5,
        metric=None,
        target=None,
        how="Consigue 10 likes en 5 artículos distintos: publica guías prácticas y compártelas en LinkedIn.",
        api_ids=("activity_badge.article.like.10x5",),
    ),
    Badge(
        key="idea_influencer",
        name="Idea Influencer",
        phase=5,
        metric=None,
        target=None,
        how="Consigue 10 votos en tus wishes: escribe el problema real, no solo la feature.",
        api_ids=("activity_badge.wish.vote.10",),
    ),
)

BY_KEY = {b.key: b for b in CATALOG}
TOTAL = len(CATALOG)

PHASE_NAMES = {
    1: "🟢 Fase 1 · Básicas",
    2: "🟡 Fase 2 · Rachas cortas",
    3: "🟠 Fase 3 · 30 días",
    4: "🔴 Fase 4 · 90 días",
    5: "🤝 Fase 5 · Impacto en comunidad",
}

REWARD_TIERS = {
    7: "🎁 ¡7 badges! Te ganaste $10 en créditos AWS.",
    14: "🎁 ¡14 badges! $20 adicionales en créditos AWS.",
    21: "🏆 ¡21 badges! Voucher de $100 para tu certificación AWS Foundational.",
}

DAILY_ROUTINE = (
    ("visit", "🔑", "Inicia sesión en Builder Center"),
    ("read", "📖", "Lee 1 artículo útil"),
    ("like", "❤️", "Dale like a lo que te sirvió"),
    ("comment", "💬", "Deja un comentario con sustancia"),
)


def _norm(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


_BY_API_ID = {api_id: b for b in CATALOG for api_id in b.api_ids}
_BY_NAME = {_norm(b.name): b for b in CATALOG}
for _b in CATALOG:
    for _alias in _b.aliases:
        _BY_NAME[_norm(_alias)] = _b


def match(badge_id: str, display_name: str) -> Badge | None:
    """Mapea una badge devuelta por la API al catálogo (por id o por nombre)."""
    return _BY_API_ID.get(badge_id) or _BY_NAME.get(_norm(display_name))
