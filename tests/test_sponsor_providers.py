from datetime import date
from decimal import Decimal

import pytest

from smikhub.services.sponsor_providers import flyer, piarflow, tgrass
from smikhub.services.sponsor_providers.common import SponsorProviderError


class _FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self):
        return self._payload


class _FakeClientSession:
    """Одна фейковая сессия, отдающая заготовленные ответы по очереди — по одному на
    каждый вызов .post(), в порядке как в реальном клиенте."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, url, **kwargs):
        self.requests.append({"method": "POST", "url": url, **kwargs})
        payload, status = self._responses.pop(0)
        return _FakeResponse(payload, status)

    def get(self, url, **kwargs):
        self.requests.append({"method": "GET", "url": url, **kwargs})
        payload, status = self._responses.pop(0)
        return _FakeResponse(payload, status)


def _patch_session(monkeypatch, module, responses):
    session = _FakeClientSession(responses)
    monkeypatch.setattr(module.aiohttp, "ClientSession", lambda: session)
    return session


@pytest.mark.asyncio
async def test_flyer_get_tasks_normalizes_response(monkeypatch):
    session = _patch_session(
        monkeypatch,
        flyer,
        [
            (
                [
                    {
                        "signature": "sig-1",
                        "task": "subscribe channel",
                        "price": "1.50",
                        "links": ["https://t.me/some_channel"],
                        "name": "Some Channel",
                        "status": "waiting",
                    }
                ],
                200,
            )
        ],
    )

    tasks = await flyer.get_tasks("api-key", user_id=42, limit=5)

    assert len(tasks) == 1
    task = tasks[0]
    assert task.provider == "flyer"
    assert task.task_id == "sig-1"
    assert task.title == "Some Channel"
    assert task.link == "https://t.me/some_channel"
    assert task.price == Decimal("1.50")
    assert task.task_type == "subscribe channel"
    assert session.requests[0]["json"]["key"] == "api-key"
    assert session.requests[0]["json"]["limit"] == 5


@pytest.mark.asyncio
async def test_flyer_check_tasks_maps_statuses(monkeypatch):
    _patch_session(
        monkeypatch,
        flyer,
        [
            ({"status": "complete"}, 200),
            ({"status": "waiting"}, 200),
            ({"status": "abort"}, 200),
        ],
    )

    statuses = await flyer.check_tasks("api-key", ["sig-1", "sig-2", "sig-3"])

    assert statuses == {"sig-1": "completed", "sig-2": "pending", "sig-3": "not_completed"}


@pytest.mark.asyncio
async def test_tgrass_get_tasks_has_no_price(monkeypatch):
    _patch_session(
        monkeypatch,
        tgrass,
        [
            (
                {
                    "status": "ok",
                    "offers": [
                        {
                            "offer_id": "off-1",
                            "name": "Some Offer",
                            "link": "https://t.me/some_offer",
                            "type": "channel",
                        }
                    ],
                },
                200,
            )
        ],
    )

    tasks = await tgrass.get_tasks("auth-key", user_id=42)

    assert len(tasks) == 1
    assert tasks[0].price is None
    assert tasks[0].task_id == "off-1"
    assert tasks[0].provider == "tgrass"


@pytest.mark.asyncio
async def test_tgrass_get_tasks_handles_no_offers(monkeypatch):
    _patch_session(monkeypatch, tgrass, [({"status": "no_offers"}, 200)])

    tasks = await tgrass.get_tasks("auth-key", user_id=42)

    assert tasks == []


@pytest.mark.asyncio
async def test_tgrass_check_tasks_maps_statuses(monkeypatch):
    _patch_session(
        monkeypatch,
        tgrass,
        [
            ({"status": "subscribed"}, 200),
            ({"status": "not_subscribed"}, 200),
        ],
    )

    statuses = await tgrass.check_tasks("auth-key", user_id=42, task_ids=["off-1", "off-2"])

    assert statuses == {"off-1": "completed", "off-2": "not_completed"}


@pytest.mark.asyncio
async def test_piarflow_get_tasks_uses_link_as_task_id(monkeypatch):
    session = _patch_session(
        monkeypatch,
        piarflow,
        [([{"link": "https://t.me/some_chat", "status": "active", "price": "2.00"}], 200)],
    )

    tasks = await piarflow.get_tasks("api-key", user_id=1, chat_id=1, max_sponsors=3)

    assert len(tasks) == 1
    assert tasks[0].task_id == "https://t.me/some_chat"
    assert tasks[0].price == Decimal("2.00")
    assert session.requests[0]["headers"]["Authorization"] == "Bearer api-key"


@pytest.mark.asyncio
async def test_piarflow_check_tasks_maps_statuses(monkeypatch):
    _patch_session(
        monkeypatch,
        piarflow,
        [
            (
                [
                    {"link": "https://t.me/a", "status": "subscribed"},
                    {"link": "https://t.me/b", "status": "not_counted"},
                ],
                200,
            )
        ],
    )

    statuses = await piarflow.check_tasks("api-key", user_id=1, task_ids=["https://t.me/a", "https://t.me/b"])

    assert statuses == {"https://t.me/a": "completed", "https://t.me/b": "pending"}


@pytest.mark.asyncio
async def test_tgrass_get_subscriber_returns_profile(monkeypatch):
    _patch_session(
        monkeypatch,
        tgrass,
        [({"id": 1, "is_premium": True, "gender": "female", "age": 22, "country": "ru"}, 200)],
    )

    profile = await tgrass.get_subscriber("auth-key", subscriber_id=1)

    assert profile is not None
    assert profile.gender == "female"
    assert profile.age == 22
    assert profile.country == "ru"


@pytest.mark.asyncio
async def test_tgrass_get_subscriber_returns_none_on_404(monkeypatch):
    _patch_session(monkeypatch, tgrass, [({}, 404)])

    profile = await tgrass.get_subscriber("auth-key", subscriber_id=999)

    assert profile is None


@pytest.mark.asyncio
async def test_tgrass_get_bot_stats_combines_balance_and_statistics(monkeypatch):
    _patch_session(
        monkeypatch,
        tgrass,
        [
            ({"balance": "12.50"}, 200),
            ({"subs_count": 10, "unsubs_count": 2, "income": "5.00"}, 200),
        ],
    )

    stats = await tgrass.get_bot_stats("auth-key", date(2026, 1, 1))

    assert stats.balance == Decimal("12.50")
    assert stats.subs_count == 10
    assert stats.unsubs_count == 2
    assert stats.income == Decimal("5.00")


@pytest.mark.asyncio
async def test_tgrass_get_bot_stats_partial_failure_keeps_other_fields(monkeypatch):
    session = _FakeClientSession([({"balance": "12.50"}, 200), ({}, 500)])
    monkeypatch.setattr(tgrass.aiohttp, "ClientSession", lambda: session)

    stats = await tgrass.get_bot_stats("auth-key", date(2026, 1, 1))

    assert stats.balance == Decimal("12.50")
    assert stats.subs_count is None


@pytest.mark.asyncio
async def test_piarflow_get_bot_stats_combines_profile_and_stats(monkeypatch):
    _patch_session(
        monkeypatch,
        piarflow,
        [
            ({"balance": "30.00"}, 200),
            ({"subs_count": 4, "unsubs_count": 1, "income": "8.00"}, 200),
        ],
    )

    stats = await piarflow.get_bot_stats("api-key", date(2026, 1, 1))

    assert stats.balance == Decimal("30.00")
    assert stats.subs_count == 4
    assert stats.income == Decimal("8.00")


@pytest.mark.asyncio
async def test_piarflow_register_bot_returns_api_key(monkeypatch):
    session = _patch_session(monkeypatch, piarflow, [({"api_key": "new-key-123"}, 200)])

    api_key = await piarflow.register_bot("123456:BOT-TOKEN", owner_chat_id=555)

    assert api_key == "new-key-123"
    assert session.requests[0]["json"] == {"chat_id": 555, "bot_token": "123456:BOT-TOKEN"}
    assert "headers" not in session.requests[0] or not session.requests[0].get("headers")


@pytest.mark.asyncio
async def test_piarflow_register_bot_raises_without_api_key(monkeypatch):
    _patch_session(monkeypatch, piarflow, [({}, 200)])

    with pytest.raises(SponsorProviderError):
        await piarflow.register_bot("123456:BOT-TOKEN", owner_chat_id=555)


@pytest.mark.asyncio
async def test_flyer_get_me_returns_key_status(monkeypatch):
    _patch_session(monkeypatch, flyer, [({"bot_id": 42, "webhook": None, "status": True}, 200)])

    info = await flyer.get_me("api-key")

    assert info == {"bot_id": 42, "webhook": None, "status": True}
