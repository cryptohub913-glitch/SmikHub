"""Клиент Send Crypto Pay API (help.send.tg) — в духе @CryptoBot Crypto Pay API.

Названия методов и полей взяты из документации (createInvoice/getInvoices/transfer,
подпись `HMAC-SHA256(sha256(token), body)`), но точный базовый URL и мелкие детали полей
в статье не были расписаны построчно — при расхождении с реальным Send API поправьте
`SEND_API_BASE_URL` и параметры запросов здесь.
"""

import hashlib
import hmac
from decimal import Decimal
from typing import Any

import aiohttp

from smikhub.config import get_settings

ASSET = "USDT"


class SendPayError(Exception):
    pass


def _headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.send_api_token:
        raise SendPayError("SEND_API_TOKEN не настроен")
    return {"Crypto-Pay-API-Token": settings.send_api_token}


async def _request(method: str, params: dict[str, Any]) -> Any:
    settings = get_settings()
    url = f"{settings.send_api_base_url.rstrip('/')}/{method}"
    async with (
        aiohttp.ClientSession() as http_session,
        http_session.post(url, json=params, headers=_headers()) as response,
    ):
        data = await response.json()

    if not data.get("ok"):
        raise SendPayError(str(data.get("error", data)))
    return data["result"]


async def create_invoice(amount: Decimal, payload: str) -> dict[str, Any]:
    return await _request(
        "createInvoice", {"asset": ASSET, "amount": str(amount), "payload": payload}
    )


async def get_invoices(invoice_ids: list[str]) -> list[dict[str, Any]]:
    result = await _request("getInvoices", {"invoice_ids": ",".join(invoice_ids)})
    return result.get("items", [])


async def transfer(telegram_user_id: int, amount: Decimal, spend_id: str) -> dict[str, Any]:
    return await _request(
        "transfer",
        {
            "user_id": telegram_user_id,
            "asset": ASSET,
            "amount": str(amount),
            "spend_id": spend_id,
        },
    )


async def check_auth() -> None:
    """Лёгкая read-only проверка, что SEND_API_TOKEN настроен и авторизуется. Ничего не
    создаёт (в отличие от createInvoice) — вызывает getInvoices с пустым списком id.
    Ничего не возвращает: любая проблема (нет токена, неверный токен, сеть) всплывает как
    SendPayError, используется в диагностике (smikhub/bot/handlers/admin.py)."""
    await get_invoices([])


def verify_signature(body: bytes, signature_header: str, api_token: str) -> bool:
    secret = hashlib.sha256(api_token.encode()).digest()
    computed = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature_header)
