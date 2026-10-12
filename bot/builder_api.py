"""Cliente de la API pública de AWS Builder Center."""

from __future__ import annotations

from dataclasses import dataclass

import requests

BASE = "https://api.builder.aws.com"
TIMEOUT = 20
HEADERS = {
    "content-type": "application/json",
    "accept": "application/json",
    "user-agent": "builder-badge-bot/1.0 (+https://github.com/davidrm-dev/builder-badge-bot)",
}


class BuilderApiError(Exception):
    pass


class ProfileNotFound(BuilderApiError):
    pass


@dataclass(frozen=True)
class Profile:
    alias: str
    builder_profile_id: str
    name: str


@dataclass(frozen=True)
class AwardedBadge:
    badge_id: str
    display_name: str
    description: str
    category: str
    awarded_epoch: float | None


def get_profile(alias: str) -> Profile:
    alias = alias.strip().lstrip("@")
    if alias.startswith("http"):
        alias = alias.rstrip("/").split("/")[-1].split("?")[0].lstrip("@")
    try:
        resp = requests.post(
            f"{BASE}/ums/getProfileByAlias",
            json={"alias": alias},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise BuilderApiError(str(exc)) from exc
    # Builder Center responde 400 a los alias con formato inválido: para el usuario es lo mismo
    # que no existir, no una caída del servicio.
    if resp.status_code in (400, 404):
        raise ProfileNotFound(alias)
    if not resp.ok:
        raise BuilderApiError(f"HTTP {resp.status_code}")
    basic = (resp.json().get("profile") or {}).get("basicInfo") or {}
    if not basic.get("builderProfileId"):
        raise ProfileNotFound(alias)
    return Profile(
        alias=basic.get("alias", alias),
        builder_profile_id=basic["builderProfileId"],
        name=basic.get("name") or basic.get("alias", alias),
    )


def get_awarded_badges(builder_profile_id: str) -> list[AwardedBadge]:
    try:
        resp = requests.get(
            f"{BASE}/rms/badges",
            params={"bpId": builder_profile_id, "locale": "en", "size": 50},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise BuilderApiError(str(exc)) from exc
    if not resp.ok:
        raise BuilderApiError(f"HTTP {resp.status_code}")
    out = []
    for item in resp.json().get("awardedBadgeList") or []:
        base = item.get("baseBadge") or {}
        out.append(
            AwardedBadge(
                badge_id=base.get("badgeId", ""),
                display_name=base.get("displayName", ""),
                description=base.get("description", ""),
                category=base.get("category", ""),
                awarded_epoch=item.get("awardedDate"),
            )
        )
    return out
