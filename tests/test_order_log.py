from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from smikhub.bot.callback_data import OrderLogCB
from smikhub.bot.handlers import order_log
from smikhub.db import order_repo, repo
from smikhub.db.models import DestinationType, TrafficType
from tests.conftest import TEST_OWNER_ID


def _make_callback(user_id: int = TEST_OWNER_ID) -> MagicMock:
    callback = MagicMock()
    callback.from_user = SimpleNamespace(id=user_id)
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


async def _running_order(session):
    await repo.get_or_create_user(session, TEST_OWNER_ID)
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, Decimal("100"))
    order = await order_repo.create_order(
        session,
        owner_id=TEST_OWNER_ID,
        traffic_type=TrafficType.SUBSCRIPTIONS,
        destination_type=DestinationType.CHANNEL_CHAT,
        destination_link="https://t.me/example_channel",
        default_price=Decimal("1.5"),
    )
    await order_repo.toggle_status(session, order)
    return order


@pytest.mark.asyncio
async def test_order_log_shows_empty_state_without_events(session):
    order = await _running_order(session)

    callback = _make_callback()
    await order_log.show_order_log(callback, OrderLogCB(order_id=order.id), session)

    sent_text = callback.message.edit_text.await_args.args[0]
    assert "Пока нет начислений" in sent_text


@pytest.mark.asyncio
async def test_order_log_renders_real_event_without_fabricated_fields(session):
    order = await _running_order(session)
    await order_repo.record_join_event(session, order, telegram_user_id=555, telegram_username="petya")

    callback = _make_callback()
    await order_log.show_order_log(callback, OrderLogCB(order_id=order.id), session)

    sent_text = callback.message.edit_text.await_args.args[0]
    assert "555" in sent_text
    assert "@petya" in sent_text
    assert "1.5" in sent_text
    assert order.destination_link in sent_text
    # No fields we can't honestly back with real data.
    assert "Telelog" not in sent_text
    assert "DC" not in sent_text


@pytest.mark.asyncio
async def test_order_log_rejects_other_users_order(session):
    order = await _running_order(session)

    callback = _make_callback(user_id=TEST_OWNER_ID + 1)
    await order_log.show_order_log(callback, OrderLogCB(order_id=order.id), session)

    callback.answer.assert_awaited_once()
    assert callback.answer.await_args.kwargs.get("show_alert") is True
    callback.message.edit_text.assert_not_awaited()
