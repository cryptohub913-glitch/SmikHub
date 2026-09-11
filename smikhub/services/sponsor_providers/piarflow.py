"""Клиент PiarFlow (piarflow.com) — написан строго по `piarflow.com/api-docs`.

Важное отличие от Flyer/Tgrass: в доступной документации у офферов PiarFlow нет отдельного
id/signature — только link/status/price. Поэтому здесь task_id — это сама ссылка, и
`/sponsors/check` тоже принимает ссылки, а не идентификаторы.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import aiohttp

from smikhub.services.sponsor_providers.common import SponsorProviderError, SponsorTask

BASE_URL = "https://piarflow.com/v1"

_STATUS_MAP = {
    "subscribed": "completed",
    "unsubscribed": "not_completed",
    "not_counted": "pending",
}


def _auth_headers(api_key: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


async def _request(path: str, api_key: str | None, params: dict[str, Any]) -> Any:
    url = f"{BASE_URL}{path}"
    async with (
        aiohttp.ClientSession() as http_session,
        http_session.post(url, json=params, headers=_auth_headers(api_key)) as response,
    ):
        if response.status >= 400:
            raise SponsorProviderError(f"piarflow {path} returned HTTP {response.status}")
        return await response.json()


async def _get(path: str, api_key: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{BASE_URL}{path}"
    async with (
        aiohttp.ClientSession() as http_session,
        http_session.get(url, params=params, headers=_auth_headers(api_key)) as response,
    ):
        if response.status >= 400:
            raise SponsorProviderError(f"piarflow {path} returned HTTP {response.status}")
        return await response.json()


def _to_price(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


async def get_tasks(
    api_key: str, user_id: int, chat_id: int, max_sponsors: int | None = None
) -> list[SponsorTask]:
    params: dict[str, Any] = {"user_id": user_id, "chat_id": chat_id}
    if max_sponsors is not None:
        params["max_sponsors"] = max_sponsors

    items = await _request("/sponsors", api_key, params)
    if not isinstance(items, list):
        return []

    return [
        SponsorTask(
            provider="piarflow",
            task_id=str(item["link"]),
            title=str(item.get("link", "")),
            link=str(item.get("link", "")),
            price=_to_price(item.get("price")),
            task_type="",
        )
        for item in items
        if "link" in item
    ]


async def check_tasks(api_key: str, user_id: int, task_ids: list[str]) -> dict[str, str]:
    data = await _request("/sponsors/check", api_key, {"user_id": user_id, "links": task_ids})
    if not isinstance(data, list):
        return {}

    results: dict[str, str] = {}
    for item in data:
        if not isinstance(item, dict) or "link" not in item:
            continue
        results[str(item["link"])] = _STATUS_MAP.get(item.get("status"), "unknown")
    return results


async def check_connection(api_key: str) -> None:
    """Лёгкая read-only проверка, что ключ реально авторизуется в PiarFlow — для
    диагностики (smikhub/bot/handlers). В отличие от get_bot_stats() ничего не
    проглатывает: любая ошибка всплывает как SponsorProviderError."""
    await _get("/traffic_bot", api_key)


async def register_bot(bot_token: str, owner_chat_id: int) -> str:
    """Регистрирует бота в PiarFlow как трафик-бота и возвращает его API-ключ.

    Заменяет ручную вставку ключа: у нас уже есть и токен бота, и Telegram ID владельца,
    так что просить пользователя идти вставлять их куда-то самому не нужно. `/traffic_bot/add`
    по документации не требует предварительного ключа — это и есть точка входа для его
    получения.
    """
    data = await _request("/traffic_bot/add", None, {"chat_id": owner_chat_id, "bot_token": bot_token})
    if not isinstance(data, dict) or not data.get("api_key"):
        raise SponsorProviderError("piarflow /traffic_bot/add did not return an api_key")
    return str(data["api_key"])


@dataclass(frozen=True)
class BotStats:
    balance: Decimal | None
    subs_count: int | None
    unsubs_count: int | None
    income: Decimal | None


def _to_decimal(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


async def get_bot_stats(api_key: str, for_date: date) -> BotStats:
    """Профиль/баланс бота и статистика за конкретный день. Как и у Tgrass, частичный
    результат (если один из двух запросов недоступен) лучше, чем полное отсутствие
    статистики."""
    balance = None
    subs_count = unsubs_count = income = None

    try:
        profile = await _get("/traffic_bot", api_key)
        if isinstance(profile, dict):
            balance = _to_decimal(profile.get("balance"))
    except SponsorProviderError:
        pass

    try:
        stats = await _get("/traffic_bot/stats", api_key, {"date": for_date.isoformat()})
        if isinstance(stats, dict):
            subs_count = stats.get("subs_count")
            unsubs_count = stats.get("unsubs_count")
            income = _to_decimal(stats.get("income"))
    except SponsorProviderError:
        pass

    return BotStats(balance=balance, subs_count=subs_count, unsubs_count=unsubs_count, income=income)
