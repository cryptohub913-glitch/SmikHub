from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from smikhub.api.routers import sponsors
from smikhub.api.schemas import CheckTaskItem, CheckTasksRequest
from smikhub.db import order_repo, repo
from smikhub.db.models import DestinationType, Provider, TrafficType
from smikhub.services.sponsor_providers.common import SponsorProviderError, SponsorTask
from tests.conftest import TEST_OWNER_ID


@pytest.fixture(autouse=True)
def _stub_tgrass_subscriber_lookup(monkeypatch):
    """get_sponsors() calls tgrass.get_subscriber() for any bot with Tgrass connected,
    regardless of which provider is under test. Default to "Tgrass doesn't know this
    user" (None) so tests don't make a real network call; tests that specifically cover
    the enrichment override this themselves."""
    monkeypatch.setattr(sponsors.tgrass, "get_subscriber", AsyncMock(return_value=None))


@pytest.fixture(autouse=True)
def _stub_flyer_get_tasks(monkeypatch):
    """_make_bot_with_integrations() always connects Flyer too, so get_sponsors() calls
    flyer.get_tasks() even in tests that aren't about Flyer. Default to no tasks so those
    tests don't make a real network call; tests that specifically cover Flyer override
    this themselves."""
    monkeypatch.setattr(sponsors.flyer, "get_tasks", AsyncMock(return_value=[]))


async def _make_bot_with_integrations(session, min_price=Decimal("1.0"), max_sponsors=3):
    await repo.get_or_create_user(session, TEST_OWNER_ID)
    bot = await repo.create_bot(
        session,
        owner_id=TEST_OWNER_ID,
        telegram_bot_id=1,
        username="sponsor_test_bot",
        bot_token="123456:AAAA",
        default_min_price=min_price,
        default_max_sponsors=max_sponsors,
    )
    await repo.connect_integration(session, bot, Provider.FLYER, "flyer-key")
    await repo.connect_integration(session, bot, Provider.TGRASS, "tgrass-key")
    token = repo.decrypt_integration_token(bot)
    # Re-fetch the way the real API dependency does, so relationships are loaded the
    # same way get_authenticated_bot would load them (selectinload via _bot_query()).
    return await repo.get_bot_by_integration_token(session, token)


@pytest.mark.asyncio
async def test_get_sponsors_filters_by_min_price_and_respects_priority(session, monkeypatch):
    bot = await _make_bot_with_integrations(session, min_price=Decimal("1.0"), max_sponsors=3)

    async def fake_flyer_get_tasks(token, user_id, limit=None):
        return [
            SponsorTask("flyer", "f1", "cheap", "https://t.me/cheap", Decimal("0.5"), "channel"),
            SponsorTask("flyer", "f2", "ok", "https://t.me/ok", Decimal("2.0"), "channel"),
        ]

    async def fake_tgrass_get_tasks(token, user_id, is_premium=False, lang="ru", limit=None):
        return [
            SponsorTask("tgrass", "t1", "no price 1", "https://t.me/t1", None, "channel"),
            SponsorTask("tgrass", "t2", "no price 2", "https://t.me/t2", None, "channel"),
        ]

    monkeypatch.setattr(sponsors.flyer, "get_tasks", fake_flyer_get_tasks)
    monkeypatch.setattr(sponsors.tgrass, "get_tasks", fake_tgrass_get_tasks)

    result = await sponsors.get_sponsors(user_id=555, chat_id=None, is_premium=False, lang="ru", bot=bot, session=session)

    # Flyer connected first -> its tasks come first; the 0.5₽ task is below min_price
    # and dropped; tgrass has no price info so it passes the filter unconditionally;
    # capped at max_sponsors=3 total.
    assert [t.task_id for t in result] == ["f2", "t1", "t2"]


@pytest.mark.asyncio
async def test_get_sponsors_stops_at_max_sponsors(session, monkeypatch):
    bot = await _make_bot_with_integrations(session, min_price=Decimal("0"), max_sponsors=1)

    async def fake_flyer_get_tasks(token, user_id, limit=None):
        return [
            SponsorTask("flyer", "f1", "a", "https://t.me/a", Decimal("1"), "channel"),
            SponsorTask("flyer", "f2", "b", "https://t.me/b", Decimal("1"), "channel"),
        ]

    monkeypatch.setattr(sponsors.flyer, "get_tasks", fake_flyer_get_tasks)

    result = await sponsors.get_sponsors(user_id=555, chat_id=None, is_premium=False, lang="ru", bot=bot, session=session)

    assert len(result) == 1
    assert result[0].task_id == "f1"


@pytest.mark.asyncio
async def test_get_sponsors_skips_provider_on_error(session, monkeypatch):
    bot = await _make_bot_with_integrations(session, min_price=Decimal("0"), max_sponsors=5)

    async def failing_get_tasks(*args, **kwargs):
        raise SponsorProviderError("network is down")

    async def fake_tgrass_get_tasks(token, user_id, is_premium=False, lang="ru", limit=None):
        return [SponsorTask("tgrass", "t1", "ok", "https://t.me/t1", None, "channel")]

    monkeypatch.setattr(sponsors.flyer, "get_tasks", failing_get_tasks)
    monkeypatch.setattr(sponsors.tgrass, "get_tasks", fake_tgrass_get_tasks)

    result = await sponsors.get_sponsors(user_id=555, chat_id=None, is_premium=False, lang="ru", bot=bot, session=session)

    # Flyer blew up but that must not take down the whole response.
    assert [t.task_id for t in result] == ["t1"]


@pytest.mark.asyncio
async def test_check_sponsors_groups_by_provider(session, monkeypatch):
    bot = await _make_bot_with_integrations(session)

    async def fake_flyer_check(token, task_ids):
        return {tid: "completed" for tid in task_ids}

    async def fake_tgrass_check(token, user_id, task_ids):
        return {tid: "not_completed" for tid in task_ids}

    monkeypatch.setattr(sponsors.flyer, "check_tasks", fake_flyer_check)
    monkeypatch.setattr(sponsors.tgrass, "check_tasks", fake_tgrass_check)

    payload = CheckTasksRequest(
        user_id=555,
        tasks=[
            CheckTaskItem(provider="flyer", task_id="f1"),
            CheckTaskItem(provider="tgrass", task_id="t1"),
        ],
    )

    result = await sponsors.check_sponsors(payload, bot=bot, session=session)

    by_provider = {(r.provider, r.task_id): r.status for r in result}
    assert by_provider == {("flyer", "f1"): "completed", ("tgrass", "t1"): "not_completed"}


@pytest.mark.asyncio
async def test_check_sponsors_unknown_for_unconnected_provider(session):
    bot = await _make_bot_with_integrations(session)  # piarflow not connected

    payload = CheckTasksRequest(user_id=555, tasks=[CheckTaskItem(provider="piarflow", task_id="x")])

    result = await sponsors.check_sponsors(payload, bot=bot, session=session)

    assert len(result) == 1
    assert result[0].status == "unknown"


async def _make_verified_order(session, price=Decimal("5")):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, Decimal("100"))
    order = await order_repo.create_order(
        session,
        owner_id=TEST_OWNER_ID,
        traffic_type=TrafficType.SUBSCRIPTIONS,
        destination_type=DestinationType.CHANNEL_CHAT,
        destination_link="https://t.me/advertiser_channel",
        default_price=price,
    )
    await order_repo.set_target_chat(session, order, chat_id=-100555)
    await order_repo.toggle_status(session, order)  # -> RUNNING
    return order


@pytest.mark.asyncio
async def test_get_sponsors_includes_native_orders(session):
    bot = await _make_bot_with_integrations(session, min_price=Decimal("1.0"), max_sponsors=5)
    order = await _make_verified_order(session, price=Decimal("3"))

    result = await sponsors.get_sponsors(user_id=999, chat_id=None, is_premium=False, lang="ru", bot=bot, session=session)

    native = [t for t in result if t.provider == "botohub"]
    assert len(native) == 1
    assert native[0].task_id == str(order.id)
    assert native[0].link == "https://t.me/advertiser_channel"
    assert native[0].price == Decimal("3")


@pytest.mark.asyncio
async def test_get_sponsors_native_orders_come_before_external(session, monkeypatch):
    # create_bot() always seeds "botohub" priority at position 0, before any connected
    # external network -> native orders should appear first in the response.
    bot = await _make_bot_with_integrations(session, min_price=Decimal("0"), max_sponsors=5)
    await _make_verified_order(session, price=Decimal("1"))

    async def fake_flyer_get_tasks(token, user_id, limit=None):
        return [SponsorTask("flyer", "f1", "flyer task", "https://t.me/flyer", Decimal("1"), "channel")]

    monkeypatch.setattr(sponsors.flyer, "get_tasks", fake_flyer_get_tasks)

    result = await sponsors.get_sponsors(
        user_id=999, chat_id=None, is_premium=False, lang="ru", bot=bot, session=session
    )

    assert result[0].provider == "botohub"
    assert result[1].provider == "flyer"


@pytest.mark.asyncio
async def test_check_sponsors_native_order_completed_after_join_event(session):
    bot = await _make_bot_with_integrations(session)
    order = await _make_verified_order(session)
    await order_repo.record_join_event(session, order, telegram_user_id=999)

    payload = CheckTasksRequest(user_id=999, tasks=[CheckTaskItem(provider="botohub", task_id=str(order.id))])
    result = await sponsors.check_sponsors(payload, bot=bot, session=session)

    assert result[0].status == "completed"


@pytest.mark.asyncio
async def test_check_sponsors_native_order_not_completed_without_join_event(session):
    bot = await _make_bot_with_integrations(session)
    order = await _make_verified_order(session)

    payload = CheckTasksRequest(user_id=999, tasks=[CheckTaskItem(provider="botohub", task_id=str(order.id))])
    result = await sponsors.check_sponsors(payload, bot=bot, session=session)

    assert result[0].status == "not_completed"


@pytest.mark.asyncio
async def test_get_sponsors_uses_tgrass_profile_to_filter_native_orders(session, monkeypatch):
    from smikhub.db.models import Gender
    from smikhub.services.sponsor_providers.tgrass import SubscriberProfile

    bot = await _make_bot_with_integrations(session, min_price=Decimal("0"), max_sponsors=5)
    male_order = await _make_verified_order(session, price=Decimal("2"))
    await order_repo.set_gender(session, male_order, Gender.MALE)

    monkeypatch.setattr(
        sponsors.tgrass,
        "get_subscriber",
        AsyncMock(return_value=SubscriberProfile(is_premium=False, gender="female", age=25, country="ru")),
    )

    result = await sponsors.get_sponsors(
        user_id=999, chat_id=None, is_premium=False, lang="ru", bot=bot, session=session
    )

    # The order is targeted at men; the (mocked) Tgrass profile says this user is a
    # woman -> the native order must not be offered, even though it's otherwise eligible.
    assert not any(t.provider == "botohub" for t in result)


@pytest.mark.asyncio
async def test_get_sponsors_tgrass_lookup_failure_does_not_break_response(session, monkeypatch):
    bot = await _make_bot_with_integrations(session, min_price=Decimal("0"), max_sponsors=5)
    await _make_verified_order(session, price=Decimal("2"))

    monkeypatch.setattr(
        sponsors.tgrass, "get_subscriber", AsyncMock(side_effect=SponsorProviderError("down"))
    )

    result = await sponsors.get_sponsors(
        user_id=999, chat_id=None, is_premium=False, lang="ru", bot=bot, session=session
    )

    # Tgrass being unreachable must not take down the whole /sponsors response — the
    # native order (with no real demographic data available) still gets offered.
    assert any(t.provider == "botohub" for t in result)
