"""Persistencia en DynamoDB (tabla única) para el despliegue serverless.

Expone la misma interfaz que `bot.db.Store`, así que el resto del bot no cambia.

Diseño de la tabla (PK/SK):
    U#<chat_id> | PROFILE                  → perfil, horario, zona
    U#<chat_id> | BADGE#<badge_id>         → badge ya otorgada por AWS
    U#<chat_id> | CHK#<YYYY-MM-DD>#<task>  → check-in manual (con TTL)
    U#<chat_id> | TIER#<n>                 → hito de recompensa ya anunciado
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr, Key

from .db import User

CHECKIN_TTL_DAYS = 400


def _pk(chat_id: int) -> str:
    return f"U#{chat_id}"


def _num(value: object, default: int = 0) -> int:
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return default


class DynamoStore:
    def __init__(self, table_name: str | None = None) -> None:
        name = table_name or os.environ["BOT_TABLE"]
        self.table = boto3.resource("dynamodb").Table(name)

    # ---------------- usuarios ----------------
    def ensure_user(self, chat_id: int) -> User:
        user = self.get_user(chat_id)
        if user:
            return user
        item = {
            "pk": _pk(chat_id),
            "sk": "PROFILE",
            "chat_id": chat_id,
            "tz": os.environ.get("BOT_DEFAULT_TZ", "America/Bogota"),
            "hour": 9,
            "minute": 0,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.table.put_item(Item=item, ConditionExpression=Attr("pk").not_exists())
        return self._to_user(item)

    def get_user(self, chat_id: int) -> User | None:
        item = self.table.get_item(Key={"pk": _pk(chat_id), "sk": "PROFILE"}).get("Item")
        return self._to_user(item) if item else None

    def all_users(self) -> list[User]:
        users: list[User] = []
        kwargs: dict = {"FilterExpression": Attr("sk").eq("PROFILE")}
        while True:
            page = self.table.scan(**kwargs)
            users.extend(self._to_user(i) for i in page.get("Items", []))
            key = page.get("LastEvaluatedKey")
            if not key:
                return users
            kwargs["ExclusiveStartKey"] = key

    @staticmethod
    def _to_user(item: dict) -> User:
        return User(
            chat_id=_num(item.get("chat_id")),
            alias=item.get("alias"),
            bp_id=item.get("bp_id"),
            name=item.get("name"),
            tz=item.get("tz") or "America/Bogota",
            hour=_num(item.get("hour"), 9),
            minute=_num(item.get("minute")),
            enabled=bool(item.get("enabled", True)),
            lang=item.get("lang") or "es",
        )

    def _update_profile(self, chat_id: int, values: dict) -> None:
        self.ensure_user(chat_id)
        names = {f"#{k}": k for k in values}
        expr = ", ".join(f"#{k} = :{k}" for k in values)
        self.table.update_item(
            Key={"pk": _pk(chat_id), "sk": "PROFILE"},
            UpdateExpression=f"SET {expr}",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues={f":{k}": v for k, v in values.items()},
        )

    def set_profile(self, chat_id: int, alias: str, bp_id: str, name: str) -> None:
        self._update_profile(chat_id, {"alias": alias, "bp_id": bp_id, "name": name})

    def set_schedule(self, chat_id: int, hour: int, minute: int) -> None:
        self._update_profile(chat_id, {"hour": hour, "minute": minute, "enabled": True})

    def set_timezone(self, chat_id: int, tz: str) -> None:
        self._update_profile(chat_id, {"tz": tz})

    def set_lang(self, chat_id: int, lang: str) -> None:
        self._update_profile(chat_id, {"lang": lang})

    def set_enabled(self, chat_id: int, enabled: bool) -> None:
        self._update_profile(chat_id, {"enabled": enabled})

    def delete_user(self, chat_id: int) -> None:
        with self.table.batch_writer() as batch:
            for item in self._items(chat_id):
                batch.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})

    def _items(self, chat_id: int, prefix: str | None = None) -> list[dict]:
        cond = Key("pk").eq(_pk(chat_id))
        if prefix:
            cond = cond & Key("sk").begins_with(prefix)
        items: list[dict] = []
        kwargs: dict = {"KeyConditionExpression": cond}
        while True:
            page = self.table.query(**kwargs)
            items.extend(page.get("Items", []))
            key = page.get("LastEvaluatedKey")
            if not key:
                return items
            kwargs["ExclusiveStartKey"] = key

    # ---------------- badges ----------------
    def known_badge_ids(self, chat_id: int) -> set[str]:
        return {i["sk"].split("#", 1)[1] for i in self._items(chat_id, "BADGE#")}

    def known_badge_keys(self, chat_id: int) -> set[str]:
        return {i["badge_key"] for i in self._items(chat_id, "BADGE#") if i.get("badge_key")}

    def save_badge(
        self,
        chat_id: int,
        badge_id: str,
        badge_key: str | None,
        display_name: str,
        epoch: float | None,
    ) -> None:
        self.table.put_item(
            Item={
                "pk": _pk(chat_id),
                "sk": f"BADGE#{badge_id}",
                "badge_key": badge_key,
                "display_name": display_name,
                "awarded_epoch": Decimal(str(epoch)) if epoch is not None else None,
            }
        )

    def badge_count(self, chat_id: int) -> int:
        return len(self._items(chat_id, "BADGE#"))

    def pending_tiers(self, chat_id: int, count: int, tiers: list[int]) -> list[int]:
        already = {int(i["sk"].split("#", 1)[1]) for i in self._items(chat_id, "TIER#")}
        new = [t for t in tiers if count >= t and t not in already]
        for tier in new:
            self.table.put_item(Item={"pk": _pk(chat_id), "sk": f"TIER#{tier}"})
        return new

    # ---------------- check-ins ----------------
    def add_checkin(self, chat_id: int, day: date, task: str) -> bool:
        ttl = int((datetime.now(timezone.utc) + timedelta(days=CHECKIN_TTL_DAYS)).timestamp())
        try:
            self.table.put_item(
                Item={
                    "pk": _pk(chat_id),
                    "sk": f"CHK#{day.isoformat()}#{task}",
                    "day": day.isoformat(),
                    "task": task,
                    "ttl": ttl,
                },
                # Escritura atómica: falla si el ítem ya existe, evita race condition
                # entre dos taps simultáneos sobre el mismo botón.
                ConditionExpression=Attr("sk").not_exists(),
            )
        except self.table.meta.client.exceptions.ConditionalCheckFailedException:
            return False
        return True

    def remove_checkin(self, chat_id: int, day: date, task: str) -> None:
        self.table.delete_item(Key={"pk": _pk(chat_id), "sk": f"CHK#{day.isoformat()}#{task}"})

    def tasks_done(self, chat_id: int, day: date) -> set[str]:
        prefix = f"CHK#{day.isoformat()}#"
        return {i["sk"][len(prefix) :] for i in self._items(chat_id, prefix)}

    def days_with_task(self, chat_id: int, task: str) -> set[date]:
        return {
            date.fromisoformat(i["day"]) for i in self._items(chat_id, "CHK#") if i["task"] == task
        }

    def set_streak(self, chat_id: int, task: str, days: int, today: date) -> None:
        """Ajusta la racha de `task` a `days` días rellenando hacia atrás con check-ins sintéticos.

        - Borra los sintéticos de hoy hacia atrás para limpiar un ajuste previo.
        - Inserta sintéticos para los `days` días que terminan hoy, incluido hoy: la racha
          declarada cuenta el día actual, y sin él la cadena se rompe mañana.
        - No toca check-ins reales (synthetic=False).
        """
        self._delete_synthetics(chat_id, task, today)

        ttl = int((datetime.now(timezone.utc) + timedelta(days=CHECKIN_TTL_DAYS)).timestamp())
        for offset in range(days):
            day = today - timedelta(days=offset)
            sk = f"CHK#{day.isoformat()}#{task}"
            try:
                self.table.put_item(
                    Item={
                        "pk": _pk(chat_id),
                        "sk": sk,
                        "day": day.isoformat(),
                        "task": task,
                        "synthetic": True,
                        "ttl": ttl,
                    },
                    # No sobreescribir un check-in real que el usuario ya marcó
                    ConditionExpression=Attr("sk").not_exists(),
                )
            except self.table.meta.client.exceptions.ConditionalCheckFailedException:
                pass  # ya existe un check-in real para ese día — perfecto, no hace falta el sintético

    def reset_streak(self, chat_id: int, task: str, today: date) -> None:
        """Reinicia la racha borrando todos los check-ins sintéticos de hoy hacia atrás."""
        self._delete_synthetics(chat_id, task, today)

    def _delete_synthetics(self, chat_id: int, task: str, until: date) -> None:
        synthetic = [
            i for i in self._items(chat_id, "CHK#")
            if i["task"] == task and i.get("synthetic") and i["day"] <= until.isoformat()
        ]
        for item in synthetic:
            self.table.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})

    def daily_streak(self, chat_id: int, task: str, today: date) -> int:
        days = self.days_with_task(chat_id, task)
        if not days:
            return 0
        cursor = today if today in days else today - timedelta(days=1)
        streak = 0
        while cursor in days:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    def weekly_streak(self, chat_id: int, task: str, today: date) -> int:
        days = self.days_with_task(chat_id, task)
        if not days:
            return 0
        weeks = {d - timedelta(days=d.weekday()) for d in days}
        current = today - timedelta(days=today.weekday())
        cursor = current if current in weeks else current - timedelta(days=7)
        streak = 0
        while cursor in weeks:
            streak += 1
            cursor -= timedelta(days=7)
        return streak

    # ---------------- control de envíos del scheduler ----------------
    def last_daily_sent(self, chat_id: int) -> str | None:
        item = self.table.get_item(Key={"pk": _pk(chat_id), "sk": "PROFILE"}).get("Item") or {}
        return item.get("last_daily")

    def mark_daily_sent(self, chat_id: int, day: date) -> None:
        self._update_profile(chat_id, {"last_daily": day.isoformat()})
