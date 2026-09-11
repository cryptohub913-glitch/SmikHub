import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from smikhub.api.main import app
from smikhub.db import platform_repo, repo
from tests.conftest import TEST_OWNER_ID, TEST_SEND_API_TOKEN


def _sign(body: bytes) -> str:
    secret = hashlib.sha256(TEST_SEND_API_TOKEN.encode()).digest()
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def _webhook_body(invoice_id: str) -> bytes:
    return json.dumps({"update_type": "invoice_paid", "payload": {"invoice_id": invoice_id}}).encode()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.asyncio
async def test_webhook_credits_balance_on_invoice_paid(session, client):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await platform_repo.create_deposit_invoice(session, user.id, "inv-1", Decimal("10"))

    body = _webhook_body("inv-1")
    response = await client.post(
        "/webhooks/send-pay",
        content=body,
        headers={"crypto-pay-api-signature": _sign(body), "content-type": "application/json"},
    )

    assert response.status_code == 200
    await session.refresh(user)
    assert Decimal(str(user.balance)) == Decimal("10")


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(session, client):
    body = _webhook_body("inv-2")
    response = await client.post(
        "/webhooks/send-pay",
        content=body,
        headers={"crypto-pay-api-signature": "not-valid", "content-type": "application/json"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_unknown_invoice(session, client):
    body = _webhook_body("does-not-exist")
    response = await client.post(
        "/webhooks/send-pay",
        content=body,
        headers={"crypto-pay-api-signature": _sign(body), "content-type": "application/json"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_webhook_is_idempotent_on_replay(session, client):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await platform_repo.create_deposit_invoice(session, user.id, "inv-3", Decimal("5"))
    body = _webhook_body("inv-3")
    headers = {"crypto-pay-api-signature": _sign(body), "content-type": "application/json"}

    await client.post("/webhooks/send-pay", content=body, headers=headers)
    await client.post("/webhooks/send-pay", content=body, headers=headers)

    await session.refresh(user)
    assert Decimal(str(user.balance)) == Decimal("5")  # not credited twice
