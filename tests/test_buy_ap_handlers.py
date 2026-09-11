from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from smikhub.bot.callback_data import OrderVerifyAdminCB
from smikhub.bot.handlers import buy_ap
from smikhub.bot.states import CreateOrderStates
from smikhub.crypto import decrypt
from smikhub.db import order_repo, repo
from smikhub.db.models import DestinationType, TrafficType
from tests.conftest import TEST_OWNER_ID

DEFAULT_TEST_ORDER_PRICE = Decimal("1.2")


def _make_state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=TEST_OWNER_ID, user_id=TEST_OWNER_ID)
    return FSMContext(storage=storage, key=key)


async def _prepared_state(traffic_type: str, destination_type: str) -> FSMContext:
    state = _make_state()
    await state.update_data(traffic_type=traffic_type, destination_type=destination_type)
    await state.set_state(CreateOrderStates.waiting_for_destination_input)
    return state


def _make_message(text: str) -> MagicMock:
    message = MagicMock()
    message.text = text
    message.from_user = SimpleNamespace(id=TEST_OWNER_ID)
    message.answer = AsyncMock()
    return message


def _make_callback() -> MagicMock:
    callback = MagicMock()
    callback.from_user = SimpleNamespace(id=TEST_OWNER_ID)
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


@pytest.mark.asyncio
async def test_resource_destination_creates_order(session):
    state = await _prepared_state("views", "resource")
    message = _make_message("https://example.com/landing")

    await buy_ap.receive_destination_input(message, session, state)

    orders = await order_repo.list_user_orders(session, TEST_OWNER_ID)
    assert len(orders) == 1
    assert orders[0].destination_type == DestinationType.RESOURCE
    assert orders[0].traffic_type == TrafficType.VIEWS
    assert orders[0].destination_link == "https://example.com/landing"
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_resource_destination_rejects_non_url(session):
    state = await _prepared_state("views", "resource")
    message = _make_message("not-a-url")

    await buy_ap.receive_destination_input(message, session, state)

    assert await order_repo.list_user_orders(session, TEST_OWNER_ID) == []
    message.answer.assert_awaited_once()
    assert "корректную ссылку" in message.answer.await_args.args[0]
    # Stays in the same state so the user can retry without restarting the wizard.
    assert await state.get_state() == CreateOrderStates.waiting_for_destination_input.state


@pytest.mark.asyncio
async def test_bot_destination_creates_order_with_encrypted_token(session, monkeypatch):
    fake_identity = SimpleNamespace(id=999, username="target_bot")
    monkeypatch.setattr(buy_ap, "fetch_bot_identity", AsyncMock(return_value=fake_identity))

    state = await _prepared_state("subscriptions", "bot")
    message = _make_message("123456:REAL-LOOKING-TOKEN")

    await buy_ap.receive_destination_input(message, session, state)

    orders = await order_repo.list_user_orders(session, TEST_OWNER_ID)
    assert len(orders) == 1
    order = orders[0]
    assert order.destination_type == DestinationType.BOT
    assert order.destination_link != "123456:REAL-LOOKING-TOKEN"  # stored encrypted
    assert decrypt(order.destination_link) == "123456:REAL-LOOKING-TOKEN"


@pytest.mark.asyncio
async def test_bot_destination_rejects_invalid_token(session, monkeypatch):
    monkeypatch.setattr(buy_ap, "fetch_bot_identity", AsyncMock(return_value=None))

    state = await _prepared_state("subscriptions", "bot")
    message = _make_message("garbage")

    await buy_ap.receive_destination_input(message, session, state)

    assert await order_repo.list_user_orders(session, TEST_OWNER_ID) == []
    assert "не удалось проверить токен" in message.answer.await_args.args[0].lower()


@pytest.mark.asyncio
async def test_channel_chat_destination_rejects_private_invite_link(session):
    state = await _prepared_state("subscriptions", "channel_chat")
    message = _make_message("https://t.me/+AbCdEfGhIjK")

    await buy_ap.receive_destination_input(message, session, state)

    assert await order_repo.list_user_orders(session, TEST_OWNER_ID) == []
    assert "публичную ссылку" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_channel_chat_destination_prompts_admin_setup(session, monkeypatch):
    fake_check_bot_identity = SimpleNamespace(id=555, username="smikhub_check_bot")
    monkeypatch.setattr(buy_ap, "fetch_bot_identity", AsyncMock(return_value=fake_check_bot_identity))
    monkeypatch.setattr(
        buy_ap, "get_settings", lambda: SimpleNamespace(check_bot_token="654321:CHECK-TOKEN")
    )

    state = await _prepared_state("subscriptions", "channel_chat")
    message = _make_message("https://t.me/my_public_channel")

    await buy_ap.receive_destination_input(message, session, state)

    orders = await order_repo.list_user_orders(session, TEST_OWNER_ID)
    assert len(orders) == 1
    assert orders[0].target_chat_id is None  # not yet verified as admin

    sent_text = message.answer.await_args.args[0]
    assert "@smikhub_check_bot" in sent_text


@pytest.mark.asyncio
async def test_verify_admin_sets_target_chat_on_success(session, monkeypatch):
    await repo.get_or_create_user(session, TEST_OWNER_ID)
    order = await order_repo.create_order(
        session,
        owner_id=TEST_OWNER_ID,
        traffic_type=TrafficType.SUBSCRIPTIONS,
        destination_type=DestinationType.CHANNEL_CHAT,
        destination_link="https://t.me/my_public_channel",
        default_price=DEFAULT_TEST_ORDER_PRICE,
    )
    monkeypatch.setattr(
        buy_ap, "get_settings", lambda: SimpleNamespace(check_bot_token="654321:CHECK-TOKEN")
    )
    monkeypatch.setattr(buy_ap, "resolve_admin_chat_id", AsyncMock(return_value=-100123456789))

    callback = _make_callback()
    await buy_ap.verify_admin(callback, OrderVerifyAdminCB(order_id=order.id), session)

    assert order.target_chat_id == -100123456789
    callback.message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_admin_rejects_when_not_confirmed(session, monkeypatch):
    await repo.get_or_create_user(session, TEST_OWNER_ID)
    order = await order_repo.create_order(
        session,
        owner_id=TEST_OWNER_ID,
        traffic_type=TrafficType.SUBSCRIPTIONS,
        destination_type=DestinationType.CHANNEL_CHAT,
        destination_link="https://t.me/my_public_channel",
        default_price=DEFAULT_TEST_ORDER_PRICE,
    )
    monkeypatch.setattr(
        buy_ap, "get_settings", lambda: SimpleNamespace(check_bot_token="654321:CHECK-TOKEN")
    )
    monkeypatch.setattr(buy_ap, "resolve_admin_chat_id", AsyncMock(return_value=None))

    callback = _make_callback()
    await buy_ap.verify_admin(callback, OrderVerifyAdminCB(order_id=order.id), session)

    assert order.target_chat_id is None
    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once()
    assert callback.answer.await_args.kwargs.get("show_alert") is True
