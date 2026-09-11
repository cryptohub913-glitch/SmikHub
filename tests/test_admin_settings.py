from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from smikhub.bot.callback_data import AdminCategoryCB, AdminSettingsCB
from smikhub.bot.handlers import add_bot, admin
from smikhub.bot.states import AdminStates
from smikhub.db import platform_repo, repo
from tests.conftest import TEST_ADMIN_ID, TEST_OWNER_ID


def _make_state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=TEST_ADMIN_ID, user_id=TEST_ADMIN_ID)
    return FSMContext(storage=storage, key=key)


def _make_callback() -> MagicMock:
    callback = MagicMock()
    callback.from_user = SimpleNamespace(id=TEST_ADMIN_ID)
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


def _make_message(text: str) -> MagicMock:
    message = MagicMock()
    message.text = text
    message.from_user = SimpleNamespace(id=TEST_ADMIN_ID)
    message.answer = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_edit_decimal_field_updates_settings(session):
    state = _make_state()
    await admin.request_field_value(
        _make_callback(), AdminSettingsCB(action="edit_field", field="sell_price_grid_min"), state
    )
    assert await state.get_state() == AdminStates.waiting_for_platform_field.state

    message = _make_message("0.7")
    await admin.receive_field_value(message, session, state)

    settings = await platform_repo.get_platform_settings(session)
    assert Decimal(str(settings.sell_price_grid_min)) == Decimal("0.7")
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_edit_int_field_stores_integer(session):
    state = _make_state()
    await state.set_state(AdminStates.waiting_for_platform_field)
    await state.update_data(field="sell_sponsors_grid_max")

    message = _make_message("15")
    await admin.receive_field_value(message, session, state)

    settings = await platform_repo.get_platform_settings(session)
    assert settings.sell_sponsors_grid_max == 15
    assert isinstance(settings.sell_sponsors_grid_max, int)


@pytest.mark.asyncio
async def test_edit_field_rejects_non_positive_value(session):
    state = _make_state()
    await state.set_state(AdminStates.waiting_for_platform_field)
    await state.update_data(field="sell_price_grid_min")

    message = _make_message("-1")
    await admin.receive_field_value(message, session, state)

    message.answer.assert_awaited_once()
    assert "положительное" in message.answer.await_args.args[0]
    # Original default is untouched.
    settings = await platform_repo.get_platform_settings(session)
    assert Decimal(str(settings.sell_price_grid_min)) == Decimal("0.5")


@pytest.mark.asyncio
async def test_add_bot_uses_platform_default_price_and_sponsors(session, monkeypatch):
    settings = await platform_repo.get_platform_settings(session)
    await platform_repo.set_platform_field(session, settings, "sell_default_min_price", Decimal("1.5"))
    await platform_repo.set_platform_field(session, settings, "sell_default_max_sponsors", 7)

    fake_identity = SimpleNamespace(id=12345, username="fresh_bot")
    monkeypatch.setattr(add_bot, "fetch_bot_identity", AsyncMock(return_value=fake_identity))

    message = _make_message("123456:SOME-TOKEN")
    message.from_user = SimpleNamespace(id=TEST_OWNER_ID)

    from smikhub.bot.states import AddBotStates

    state = _make_state()
    await state.set_state(AddBotStates.waiting_for_token)

    await add_bot.receive_bot_token(message, session, state)

    bot = await repo.get_bot_by_telegram_id(session, 12345)
    assert Decimal(str(bot.min_price)) == Decimal("1.5")
    assert bot.max_sponsors == 7


@pytest.mark.asyncio
async def test_category_add_rename_delete_flow(session):
    add_callback = _make_callback()
    await admin.request_new_category(add_callback, _make_state())

    state = _make_state()
    await state.set_state(AdminStates.waiting_for_category_title)
    await state.update_data(category_id=None)
    await admin.receive_category_title(_make_message("Гемблинг"), session, state)

    categories = await repo.list_categories(session)
    created = next(c for c in categories if c.title == "Гемблинг")
    assert created.code  # auto-generated slug

    rename_state = _make_state()
    await rename_state.set_state(AdminStates.waiting_for_category_title)
    await rename_state.update_data(category_id=created.id)
    await admin.receive_category_title(_make_message("Казино"), session, rename_state)

    renamed = await session.get(type(created), created.id)
    assert renamed.title == "Казино"

    callback = _make_callback()
    await admin.delete_category(callback, AdminCategoryCB(action="delete_yes", category_id=created.id), session)

    remaining_codes = {c.id for c in await repo.list_categories(session)}
    assert created.id not in remaining_codes


@pytest.mark.asyncio
async def test_create_category_dedupes_slug(session):
    first = await repo.create_category(session, "Крипта")
    second = await repo.create_category(session, "Крипта")

    assert first.code != second.code
