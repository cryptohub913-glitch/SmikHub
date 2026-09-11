from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from smikhub.api.main import app
from smikhub.db import repo
from smikhub.db.models import Provider
from tests.conftest import TEST_OWNER_ID


async def _make_bot(session):
    await repo.get_or_create_user(session, TEST_OWNER_ID)
    return await repo.create_bot(
        session,
        owner_id=TEST_OWNER_ID,
        telegram_bot_id=42,
        username="test_bot",
        bot_token="123456:AAAABBBBCCCC",
        default_min_price=Decimal("0.0"),
        default_max_sponsors=3,
    )


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.asyncio
async def test_config_requires_auth_header(client):
    response = await client.get("/api/v1/bot/config")
    assert response.status_code == 422  # missing required header


@pytest.mark.asyncio
async def test_config_rejects_unknown_token(client):
    response = await client.get("/api/v1/bot/config", headers={"Auth": "not-a-real-token"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_config_returns_bot_settings_for_valid_token(session, client):
    bot = await _make_bot(session)
    await repo.connect_integration(session, bot, Provider.SUBGRAM, "subgram-token")
    token = repo.decrypt_integration_token(bot)

    response = await client.get("/api/v1/bot/config", headers={"Auth": token})

    assert response.status_code == 200
    body = response.json()
    assert body["bot_username"] == "test_bot"
    assert body["is_active"] is True
    assert body["category_mode"] == "all_except_own"
    assert body["provider_priority"] == ["botohub", "subgram"]
    assert body["disabled_categories"] == []


@pytest.mark.asyncio
async def test_config_rejects_inactive_bot(session, client):
    bot = await _make_bot(session)
    await repo.toggle_active(session, bot)
    token = repo.decrypt_integration_token(bot)

    response = await client.get("/api/v1/bot/config", headers={"Auth": token})

    assert response.status_code == 401
