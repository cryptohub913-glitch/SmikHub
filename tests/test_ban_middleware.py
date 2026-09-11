from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Update

from smikhub.bot.middlewares import BanCheckMiddleware
from smikhub.db import repo
from smikhub.db.platform_repo import toggle_ban
from tests.conftest import TEST_OWNER_ID


def _make_update_with_message(user_id: int) -> tuple[MagicMock, MagicMock]:
    update = MagicMock(spec=Update)
    message = MagicMock()
    message.from_user = SimpleNamespace(id=user_id)
    message.answer = AsyncMock()
    update.message = message
    update.callback_query = None
    return update, message


@pytest.mark.asyncio
async def test_ban_middleware_blocks_banned_user(session):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await toggle_ban(session, user)

    update, message = _make_update_with_message(TEST_OWNER_ID)
    handler = AsyncMock()
    middleware = BanCheckMiddleware()

    result = await middleware(handler, update, {"session": session})

    handler.assert_not_awaited()
    message.answer.assert_awaited_once()
    assert result is None


@pytest.mark.asyncio
async def test_ban_middleware_allows_active_user(session):
    await repo.get_or_create_user(session, TEST_OWNER_ID)

    update, _message = _make_update_with_message(TEST_OWNER_ID)
    handler = AsyncMock(return_value="handled")
    middleware = BanCheckMiddleware()

    result = await middleware(handler, update, {"session": session})

    handler.assert_awaited_once_with(update, {"session": session})
    assert result == "handled"


@pytest.mark.asyncio
async def test_ban_middleware_allows_unknown_user(session):
    # A user that has never interacted with the bot yet (no row in DB) must not be blocked.
    update, _message = _make_update_with_message(555_444_333)
    handler = AsyncMock(return_value="handled")
    middleware = BanCheckMiddleware()

    result = await middleware(handler, update, {"session": session})

    handler.assert_awaited_once()
    assert result == "handled"
