"""Клиент Tgrass (tgrass.space) — написан строго по `tgrass.space/integration`.

Важное ограничение: в доступной документации `/offers` не отдаёт цену за оффер — только
name/link/type/offer_id. Поэтому SponsorTask.price здесь всегда None, и фильтр "мин. цена"
бота к задачам Tgrass не применяется (см. smikhub/api/routers/sponsors.py).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import aiohttp

from smikhub.services.sponsor_providers.common import SponsorProviderError, SponsorTask

BASE_URL = "https://tgrass.space"

_CHECK_STATUS_MAP = {
    "subscribed": "completed",
    "not_subscribed": "not_completed",
    "user_not_found": "unknown",
    "offer_not_found": "unknown",
    "offer_expired": "unknown",
}


async def _request(path: str, api_key: str, params: dict[str, Any]) -> Any:
    url = f"{BASE_URL}{path}"
    headers = {"Auth": api_key}
    async with (
        aiohttp.ClientSession() as http_session,
        http_session.post(url, json=params, headers=headers) as response,
    ):
        if response.status >= 400:
            raise SponsorProviderError(f"tgrass {path} returned HTTP {response.status}")
        return await response.json()


async def _get(path: str, api_key: str, params: dict[str, Any] | None = None) -> tuple[int, Any]:
    url = f"{BASE_URL}{path}"
    headers = {"Auth": api_key}
    async with (
        aiohttp.ClientSession() as http_session,
        http_session.get(url, params=params, headers=headers) as response,
    ):
        if response.status >= 400 and response.status != 404:
            raise SponsorProviderError(f"tgrass {path} returned HTTP {response.status}")
        return response.status, await response.json()


async def get_tasks(
    api_key: str,
    user_id: int,
    is_premium: bool = False,
    lang: str = "ru",
    limit: int | None = None,
) -> list[SponsorTask]:
    params: dict[str, Any] = {"tg_user_id": user_id, "is_premium": is_premium, "lang": lang}
    if limit is not None:
        params["offers_limit"] = limit

    data = await _request("/offers", api_key, params)
    if not isinstance(data, dict) or data.get("status") == "no_offers":
        return []

    offers = data.get("offers", [])
    return [
        SponsorTask(
            provider="tgrass",
            task_id=str(offer["offer_id"]),
            title=str(offer.get("name", "")),
            link=str(offer.get("link", "")),
            price=None,  # Tgrass не отдаёт цену оффера в /offers
            task_type=str(offer.get("type", "")),
        )
        for offer in offers
        if "offer_id" in offer
    ]


async def check_tasks(api_key: str, user_id: int, task_ids: list[str]) -> dict[str, str]:
    results: dict[str, str] = {}
    for offer_id in task_ids:
        data = await _request("/check", api_key, {"tg_user_id": user_id, "offer_id": offer_id})
        raw_status = data.get("status") if isinstance(data, dict) else data
        results[offer_id] = _CHECK_STATUS_MAP.get(raw_status, "unknown")
    return results


async def check_connection(api_key: str) -> None:
    """Лёгкая read-only проверка, что ключ реально авторизуется в Tgrass — для
    диагностики (smikhub/bot/handlers). В отличие от get_bot_stats() ничего не
    проглатывает: любая ошибка (включая 404 — для /balance это тоже признак проблемы,
    в отличие от get_subscriber, где 404 — легитимный "юзер неизвестен") всплывает как
    SponsorProviderError."""
    status, _data = await _get("/balance", api_key)
    if status != 200:
        raise SponsorProviderError(f"tgrass /balance returned HTTP {status}")


@dataclass(frozen=True)
class SubscriberProfile:
    """То, что реально знает Tgrass о пользователе — только если он уже встречался их
    сети. Поля могут быть None, если Tgrass их не прислал."""

    is_premium: bool | None
    gender: str | None
    age: int | None
    country: str | None


async def get_subscriber(api_key: str, subscriber_id: int) -> SubscriberProfile | None:
    """Профиль подписчика по данным Tgrass. None — если Tgrass его не знает (404) или не
    прислал данных; это ожидаемая ситуация, а не ошибка."""
    status, data = await _get(f"/subscriber/{subscriber_id}", api_key)
    if status == 404 or not isinstance(data, dict):
        return None
    return SubscriberProfile(
        is_premium=data.get("is_premium"),
        gender=data.get("gender"),
        age=data.get("age"),
        country=data.get("country"),
    )


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
    """Баланс бота и статистика за конкретный день. Если один из двух запросов
    недоступен — соответствующие поля останутся None, это не считается фатальной ошибкой
    (частично показать статистику лучше, чем не показать её вовсе)."""
    balance = None
    subs_count = unsubs_count = income = None

    try:
        _status, balance_data = await _get("/balance", api_key)
        if isinstance(balance_data, dict):
            balance = _to_decimal(balance_data.get("balance"))
    except SponsorProviderError:
        pass

    try:
        _status, stats_data = await _get("/statistics", api_key, {"date": for_date.isoformat()})
        if isinstance(stats_data, dict):
            subs_count = stats_data.get("subs_count")
            unsubs_count = stats_data.get("unsubs_count")
            income = _to_decimal(stats_data.get("income"))
    except SponsorProviderError:
        pass

    return BotStats(balance=balance, subs_count=subs_count, unsubs_count=unsubs_count, income=income)
