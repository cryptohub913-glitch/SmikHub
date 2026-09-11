from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from smikhub.bot.callback_data import IntegrationCB
from smikhub.bot.handlers import integrations
from smikhub.crypto import decrypt
from smikhub.db import repo
from smikhub.db.models import Provider
from smikhub.services.sponsor_providers.common import SponsorProviderError
from tests.conftest import TEST_OWNER_ID


def _make_state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=TEST_OWNER_ID, user_id=TEST_OWNER_ID)
    return FSMContext(storage=storage, key=key)


def _make_callback() -> MagicMock:
    callback = MagicMock()
    callback.from_user = SimpleNamespace(id=TEST_OWNER_ID)
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


async def _make_bot(session):
    await repo.get_or_create_user(session, TEST_OWNER_ID)
    return await repo.create_bot(
        session,
        owner_id=TEST_OWNER_ID,
        telegram_bot_id=1,
        username="piarflow_test_bot",
        bot_token="123456:REAL-BOT-TOKEN",
        default_min_price=Decimal("0.0"),
        default_max_sponsors=3,
    )


@pytest.mark.asyncio
async def test_auto_connect_piarflow_success(session, monkeypatch):
    bot = await _make_bot(session)
    monkeypatch.setattr(
        integrations.piarflow, "register_bot", AsyncMock(return_value="new-piarflow-key")
    )

    callback = _make_callback()
    state = _make_state()
    await integrations.auto_connect_piarflow(
        callback, IntegrationCB(action="auto_connect", bot_id=bot.id, provider="piarflow"), session, state
    )

    integrations.piarflow.register_bot.assert_awaited_once_with(
        "123456:REAL-BOT-TOKEN", owner_chat_id=TEST_OWNER_ID
    )
    refreshed = await repo.get_bot(session, bot.id)
    piarflow_integration = next(i for i in refreshed.integrations if i.provider == Provider.PIARFLOW)
    assert decrypt(piarflow_integration.encrypted_token) == "new-piarflow-key"
    callback.message.edit_text.assert_awaited_once()
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_auto_connect_piarflow_failure_keeps_manual_fallback_available(session, monkeypatch):
    bot = await _make_bot(session)
    monkeypatch.setattr(
        integrations.piarflow, "register_bot", AsyncMock(side_effect=SponsorProviderError("boom"))
    )

    callback = _make_callback()
    state = _make_state()
    await integrations.auto_connect_piarflow(
        callback, IntegrationCB(action="auto_connect", bot_id=bot.id, provider="piarflow"), session, state
    )

    refreshed = await repo.get_bot(session, bot.id)
    assert refreshed.integrations == []
    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once()
    assert callback.answer.await_args.kwargs.get("show_alert") is True
