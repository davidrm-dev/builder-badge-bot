"""Catálogo de las 21 badges de AWS Builder Center, enlaces útiles y consejos bilingües."""

from __future__ import annotations

from dataclasses import dataclass, field

BASE = "https://builder.aws.com"
LINKS = {
    "home": f"{BASE}/",
    "learn": f"{BASE}/learn",
    "write": f"{BASE}/create/content",
    "wishlist": f"{BASE}/wishlist",
    "new_wish": f"{BASE}/create/wish",
    "profile": f"{BASE}/profile",
    "settings": f"{BASE}/settings",
    "rewards": f"{BASE}/profile/rewards",
    "spaces": f"{BASE}/connect/spaces",
}


def profile_url(alias: str) -> str:
    return f"{BASE}/community/@{alias}?tab=badges"


@dataclass(frozen=True)
class Badge:
    key: str
    name: str
    phase: int
    metric: str | None  # visit | like | comment | article_week | wish_vote_week | None
    target: int | None  # días/semanas de racha necesarios
    how_es: str
    how_en: str
    link: str = "home"  # clave de LINKS: a dónde mandar al usuario para trabajarla
    api_ids: tuple[str, ...] = ()
    aliases: tuple[str, ...] = field(default=())

    def how(self, lang: str) -> str:
        return self.how_en if lang == "en" else self.how_es

    @property
    def url(self) -> str:
        return LINKS[self.link]


CATALOG: tuple[Badge, ...] = (
    Badge(
        key="hello_world",
        name="Hello, World!",
        phase=1,
        metric=None,
        target=None,
        how_es="Completa la sección About de tu perfil: bio, ubicación y redes. 2 minutos.",
        how_en="Fill in the About section of your profile: bio, location and links. 2 minutes.",
        link="settings",
        api_ids=("activity_badge.profile.about",),
    ),
    Badge(
        key="photo_finisher",
        name="Photo Finisher",
        phase=1,
        metric=None,
        target=None,
        how_es="Sube una foto de perfil y guarda los cambios.",
        how_en="Upload a profile picture and save.",
        link="settings",
        api_ids=("activity_badge.profile.photo",),
    ),
    Badge(
        key="knowledge_seeker",
        name="Knowledge Seeker",
        phase=1,
        metric=None,
        target=None,
        how_es="Lee 10 artículos distintos. Elige temas que estés estudiando: Lambda, S3, Bedrock…",
        how_en="Read 10 different articles. Pick topics you are studying: Lambda, S3, Bedrock…",
        link="learn",
        api_ids=("activity_badge.article.10read",),
    ),
    Badge(
        key="discussion_debut",
        name="Discussion Debut",
        phase=1,
        metric=None,
        target=None,
        how_es="Deja tu primer comentario. Truco: cuenta cómo aplicaste lo que leíste.",
        how_en="Leave your first comment. Tip: say how you applied what you just read.",
        link="learn",
        api_ids=("activity_badge.comment.first",),
    ),
    Badge(
        key="first_article",
        name="First Article",
        phase=1,
        metric=None,
        target=None,
        how_es="Publica tu primer artículo: algo que aprendiste, construiste o depuraste esta semana.",
        how_en="Publish your first article: something you learned, built or debugged this week.",
        link="write",
        api_ids=("activity_badge.article.first",),
    ),
    Badge(
        key="first_wish",
        name="First Wish",
        phase=1,
        metric=None,
        target=None,
        how_es="Publica tu primer Wish. Busca antes para no duplicar y describe el problema, no la feature.",
        how_en="Post your first Wish. Search first to avoid duplicates and describe the problem, not the feature.",
        link="new_wish",
        api_ids=("activity_badge.wish.first",),
    ),
    Badge(
        key="visit_7",
        name="7-Day Visit Streak",
        phase=2,
        metric="visit",
        target=7,
        how_es="Inicia sesión en Builder Center 7 días seguidos. Es la más fácil: 10 segundos al día.",
        how_en="Sign in to Builder Center 7 days in a row. The easiest one: 10 seconds a day.",
        api_ids=("activity_badge.visitor.streak.7day",),
    ),
    Badge(
        key="like_7",
        name="7-Day Like Streak",
        phase=2,
        metric="like",
        target=7,
        how_es="Dale like a algo útil cada día, 7 días seguidos. Aprovecha el artículo que ya leíste.",
        how_en="Like something useful every day for 7 days. Use the article you already read.",
        link="learn",
        api_ids=("activity_badge.like.streak.7day",),
    ),
    Badge(
        key="comment_7",
        name="7-Day Comment Streak",
        phase=2,
        metric="comment",
        target=7,
        how_es="Comenta con sustancia cada día, 7 días seguidos. 2 frases y una pregunta bastan.",
        how_en="Leave a substantive comment every day for 7 days. Two sentences and a question is enough.",
        link="learn",
        api_ids=("activity_badge.comment.streak.7day",),
    ),
    Badge(
        key="wish_vote_4w",
        name="4-Week Wish Vote Streak",
        phase=2,
        metric="wish_vote_week",
        target=4,
        how_es="Vota wishes al menos una vez por semana, 4 semanas seguidas.",
        how_en="Vote on wishes at least once a week, 4 weeks in a row.",
        link="wishlist",
        api_ids=("activity_badge.wishvote.streak.4week", "activity_badge.wish.vote.streak.4week"),
    ),
    Badge(
        key="article_4w",
        name="4-Week Article Publishing Streak",
        phase=2,
        metric="article_week",
        target=4,
        how_es="Publica un artículo por semana, 4 semanas seguidas. Escribe corto y práctico.",
        how_en="Publish one article per week for 4 weeks. Keep it short and practical.",
        link="write",
        api_ids=("activity_badge.article.streak.4week",),
    ),
    Badge(
        key="visit_30",
        name="30-Day Visit Streak",
        phase=3,
        metric="visit",
        target=30,
        how_es="Mantén el sign-in diario hasta 30 días seguidos.",
        how_en="Keep the daily sign-in going to 30 days in a row.",
        api_ids=("activity_badge.visitor.streak.30day",),
    ),
    Badge(
        key="like_30",
        name="30-Day Like Streak",
        phase=3,
        metric="like",
        target=30,
        how_es="Mantén el like diario hasta 30 días seguidos.",
        how_en="Keep the daily like going to 30 days in a row.",
        link="learn",
        api_ids=("activity_badge.like.streak.30day",),
    ),
    Badge(
        key="comment_30",
        name="30-Day Comment Streak",
        phase=3,
        metric="comment",
        target=30,
        how_es="Mantén el comentario diario hasta 30 días seguidos.",
        how_en="Keep the daily comment going to 30 days in a row.",
        link="learn",
        api_ids=("activity_badge.comment.streak.30day",),
    ),
    Badge(
        key="visit_90",
        name="90-Day Visit Streak",
        phase=4,
        metric="visit",
        target=90,
        how_es="Sign-in diario durante 90 días. Es la más larga: empieza hoy, no en enero.",
        how_en="Daily sign-in for 90 days. It is the longest one: start today, not in January.",
        api_ids=("activity_badge.visitor.streak.90day",),
    ),
    Badge(
        key="like_90",
        name="90-Day Like Streak",
        phase=4,
        metric="like",
        target=90,
        how_es="Like diario durante 90 días seguidos.",
        how_en="Daily like for 90 days in a row.",
        link="learn",
        api_ids=("activity_badge.like.streak.90day",),
    ),
    Badge(
        key="comment_90",
        name="90-Day Comment Streak",
        phase=4,
        metric="comment",
        target=90,
        how_es="Comentario diario durante 90 días seguidos.",
        how_en="Daily comment for 90 days in a row.",
        link="learn",
        api_ids=("activity_badge.comment.streak.90day",),
    ),
    Badge(
        key="conversation_starter",
        name="Conversation Starter",
        phase=5,
        metric=None,
        target=None,
        how_es="Consigue respuestas en 10 comentarios tuyos: termina siempre con una pregunta abierta.",
        how_en="Get replies on 10 of your comments: always end with an open question.",
        link="learn",
        api_ids=("activity_badge.comment.reply.10",),
    ),
    Badge(
        key="meaningful_contributor",
        name="Meaningful Contributor",
        phase=5,
        metric=None,
        target=None,
        how_es="10 likes en 5 comentarios distintos: aporta un dato, un error que cometiste o un tip concreto.",
        how_en="10 likes across 5 different comments: add a fact, a mistake you made, or a concrete tip.",
        link="learn",
        api_ids=("activity_badge.comment.like.10x5",),
    ),
    Badge(
        key="valued_creator",
        name="Valued Creator",
        phase=5,
        metric=None,
        target=None,
        how_es="10 likes en 5 artículos distintos: guías prácticas y compártelas en LinkedIn.",
        how_en="10 likes across 5 different articles: practical guides, then share them on LinkedIn.",
        link="write",
        api_ids=("activity_badge.article.like.10x5",),
    ),
    Badge(
        key="idea_influencer",
        name="Idea Influencer",
        phase=5,
        metric=None,
        target=None,
        how_es="10 votos en tus wishes: escribe el problema real y compártelo con tu comunidad.",
        how_en="10 votes on your wishes: write the real problem and share it with your community.",
        link="wishlist",
        api_ids=("activity_badge.wish.vote.10",),
    ),
)

BY_KEY = {b.key: b for b in CATALOG}
TOTAL = len(CATALOG)

PHASE_NAMES = {
    "es": {
        1: "🟢 Fase 1 · Básicas",
        2: "🟡 Fase 2 · Rachas cortas",
        3: "🟠 Fase 3 · 30 días",
        4: "🔴 Fase 4 · 90 días",
        5: "🤝 Fase 5 · Impacto en comunidad",
    },
    "en": {
        1: "🟢 Phase 1 · Quick wins",
        2: "🟡 Phase 2 · Short streaks",
        3: "🟠 Phase 3 · 30 days",
        4: "🔴 Phase 4 · 90 days",
        5: "🤝 Phase 5 · Community impact",
    },
}

REWARD_TIERS = {
    "es": {
        7: "🎁 ¡7 badges! Te ganaste $10 en créditos AWS.",
        14: "🎁 ¡14 badges! $20 adicionales en créditos AWS.",
        21: "🏆 ¡21 badges! Voucher de $100 para tu certificación AWS Foundational.",
    },
    "en": {
        7: "🎁 7 badges! You just earned $10 in AWS credits.",
        14: "🎁 14 badges! $20 more in AWS credits.",
        21: "🏆 21 badges! A $100 voucher for your AWS Foundational certification.",
    },
}
TIER_VALUES = tuple(sorted(REWARD_TIERS["es"]))

DAILY_ROUTINE = (
    ("visit", "🔑", "Inicia sesión en Builder Center", "Sign in to Builder Center", "home"),
    ("read", "📖", "Lee 1 artículo útil", "Read 1 useful article", "learn"),
    ("like", "❤️", "Dale like a lo que te sirvió", "Like what helped you", "learn"),
    ("comment", "💬", "Deja un comentario con sustancia", "Leave a substantive comment", "learn"),
)

WEEKLY_ROUTINE = (
    ("article_week", "📝", "Publica el artículo de la semana", "Publish this week's article", "write"),
    ("wish_vote_week", "💡", "Vota un wish esta semana", "Vote a wish this week", "wishlist"),
)

ROUTINE_TEXT = {task: (es, en) for task, _icon, es, en, _link in DAILY_ROUTINE + WEEKLY_ROUTINE}
ROUTINE_LINK = {task: link for task, _icon, _es, _en, link in DAILY_ROUTINE + WEEKLY_ROUTINE}


def routine_text(task: str, lang: str) -> str:
    es, en = ROUTINE_TEXT[task]
    return en if lang == "en" else es


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
