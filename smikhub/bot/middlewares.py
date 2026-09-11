from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from smikhub.db.models import User

BANNED_TEXT = "🚫 Вы заблокированы на платформе."


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._session_factory() as session:
            data["session"] = session
            return await handler(event, data)


class BanCheckMiddleware(BaseMiddleware):
    """Блокирует дальнейшую обработку апдейтов от забаненных пользователей.

    Должна быть зарегистрирована после DbSessionMiddleware — использует уже
    подготовленную сессию из data["session"].
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Update):
            user_id = _extract_user_id(event)
            if user_id is not None:
                session: AsyncSession = data["session"]
                user = await session.get(User, user_id)
                if user is not None and user.is_banned:
                    await _notify_banned(event)
                    return None
        return await handler(event, data)


def _extract_user_id(update: Update) -> int | None:
    if update.message is not None:
        return update.message.from_user.id
    if update.callback_query is not None:
        return update.callback_query.from_user.id
    return None


async def _notify_banned(update: Update) -> None:
    if update.callback_query is not None:
        await update.callback_query.answer(BANNED_TEXT, show_alert=True)
    elif update.message is not None:
        await update.message.answer(BANNED_TEXT)
