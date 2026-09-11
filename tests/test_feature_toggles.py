from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from smikhub.bot.handlers import add_bot, buy_ap
from smikhub.db import platform_repo
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


@pytest.mark.asyncio
async def test_sell_ap_disabled_shows_section_disabled(session):
    settings = await platform_repo.get_platform_settings(session)
    await platform_repo.toggle_sell_ap_enabled(session, settings)

    callback = _make_callback()
    await add_bot.show_sell_ap(callback, session, _make_state())

    sent_text = callback.message.edit_text.await_args.args[0]
    assert "отключён" in sent_text


@pytest.mark.asyncio
async def test_sell_ap_enabled_shows_normal_screen(session):
    callback = _make_callback()
    await add_bot.show_sell_ap(callback, session, _make_state())

    sent_text = callback.message.edit_text.await_args.args[0]
    assert "отключён" not in sent_text


@pytest.mark.asyncio
async def test_buy_ap_disabled_shows_section_disabled(session):
    settings = await platform_repo.get_platform_settings(session)
    await platform_repo.toggle_buy_ap_enabled(session, settings)

    callback = _make_callback()
    await buy_ap.show_buy_ap(callback, session, _make_state())

    sent_text = callback.message.edit_text.await_args.args[0]
    assert "отключён" in sent_text
