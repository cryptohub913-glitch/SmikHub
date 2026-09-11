from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from smikhub.bot.handlers import add_bot
from smikhub.bot.states import AddBotStates
from smikhub.db import repo
from tests.conftest import TEST_OWNER_ID


def _make_state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=TEST_OWNER_ID, user_id=TEST_OWNER_ID)
    return FSMContext(storage=storage, key=key)


def _make_message(text: str) -> MagicMock:
    message = MagicMock()
    message.text = text
    message.from_user = SimpleNamespace(id=TEST_OWNER_ID)
    message.answer = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_receive_bot_token_creates_bot_on_valid_token(session, monkeypatch):
    fake_identity = SimpleNamespace(id=999, username="my_shop_bot")
    monkeypatch.setattr(add_bot, "fetch_bot_identity", AsyncMock(return_value=fake_identity))

    state = _make_state()
    await state.set_state(AddBotStates.waiting_for_token)
    message = _make_message("123456:REAL-LOOKING-TOKEN")

    await add_bot.receive_bot_token(message, session, state)

    message.answer.assert_awaited_once()
    sent_text = message.answer.await_args.args[0]
    assert "@my_shop_bot" in sent_text
    assert await state.get_state() is None

    created = await repo.get_bot_by_telegram_id(session, 999)
    assert created is not None
    assert created.owner_id == TEST_OWNER_ID


@pytest.mark.asyncio
async def test_receive_bot_token_rejects_invalid_token(session, monkeypatch):
    monkeypatch.setattr(add_bot, "fetch_bot_identity", AsyncMock(return_value=None))

    state = _make_state()
    await state.set_state(AddBotStates.waiting_for_token)
    message = _make_message("not-a-token")

    await add_bot.receive_bot_token(message, session, state)

    message.answer.assert_awaited_once()
    assert "не удалось проверить токен" in message.answer.await_args.args[0].lower()
    # State is preserved so the user can retry without restarting the flow.
    assert await state.get_state() == AddBotStates.waiting_for_token.state


@pytest.mark.asyncio
async def test_receive_bot_token_rejects_already_registered_bot(session, monkeypatch):
    await repo.get_or_create_user(session, TEST_OWNER_ID)
    await repo.create_bot(
        session,
        owner_id=TEST_OWNER_ID,
        telegram_bot_id=999,
        username="my_shop_bot",
        bot_token="123456:ORIGINAL-TOKEN",
        default_min_price=Decimal("0.0"),
        default_max_sponsors=3,
    )

    fake_identity = SimpleNamespace(id=999, username="my_shop_bot")
    monkeypatch.setattr(add_bot, "fetch_bot_identity", AsyncMock(return_value=fake_identity))

    state = _make_state()
    await state.set_state(AddBotStates.waiting_for_token)
    message = _make_message("123456:SAME-BOT-DIFFERENT-TOKEN")

    await add_bot.receive_bot_token(message, session, state)

    assert "уже подключён" in message.answer.await_args.args[0]
    bots = await repo.list_user_bots(session, TEST_OWNER_ID)
    assert len(bots) == 1
