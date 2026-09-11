"""Клиент Flyer (api.flyerhubs.com) — сервис, уже упоминаемый в боте под кнопкой "✅ Flyer".

Написан строго по `https://api.flyerhubs.com/openapi.json` (ReDoc сам по себе рендерится
в браузере, спека читается напрямую). Ключ API передаётся в теле запроса полем "key", а не
заголовком — так задокументировано у Flyer, в отличие от остальных провайдеров.
"""

from decimal import Decimal, InvalidOperation
from typing import Any

import aiohttp

from smikhub.services.sponsor_providers.common import SponsorProviderError, SponsorTask

BASE_URL = "https://api.flyerhubs.com"

_STATUS_MAP = {
    "complete": "completed",
    "waiting": "pending",
    "incomplete": "not_completed",
    "abort": "not_completed",
    "unavailable": "unknown",
}


async def _request(method: str, params: dict[str, Any]) -> Any:
    url = f"{BASE_URL}/{method}"
    async with (
        aiohttp.ClientSession() as http_session,
        http_session.post(url, json=params) as response,
    ):
        if response.status >= 400:
            raise SponsorProviderError(f"flyer {method} returned HTTP {response.status}")
        return await response.json()


def _to_price(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


def _to_link(raw: Any) -> str:
    if isinstance(raw, list):
        return raw[0] if raw else ""
    return raw or ""


async def get_tasks(api_key: str, user_id: int, limit: int | None = None) -> list[SponsorTask]:
    params: dict[str, Any] = {"key": api_key, "user_id": user_id}
    if limit is not None:
        params["limit"] = min(limit, 10)  # задокументированный максимум у Flyer

    items = await _request("get_tasks", params)
    if not isinstance(items, list):
        return []

    return [
        SponsorTask(
            provider="flyer",
            task_id=str(item["signature"]),
            title=str(item.get("name", "")),
            link=_to_link(item.get("links")),
            price=_to_price(item.get("price")),
            task_type=str(item.get("task", "")),
        )
        for item in items
        if "signature" in item
    ]


async def check_tasks(api_key: str, task_ids: list[str]) -> dict[str, str]:
    results: dict[str, str] = {}
    for signature in task_ids:
        data = await _request("check_task", {"key": api_key, "signature": signature})
        raw_status = data.get("status") if isinstance(data, dict) else data
        results[signature] = _STATUS_MAP.get(raw_status, "unknown")
    return results


async def get_me(api_key: str) -> dict[str, Any]:
    """Статус самого ключа: bot_id/webhook/status. Flyer, по доступной документации, не
    отдаёт отдельной агрегированной статистики бота (дохода, начислений) — только это."""
    data = await _request("get_me", {"key": api_key})
    return data if isinstance(data, dict) else {}
