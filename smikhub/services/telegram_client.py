import re

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.types import User as TelegramUser

_USERNAME_RE = re.compile(r"^(?:https?://)?(?:t\.me/|telegram\.me/)?@?([A-Za-z0-9_]{5,32})/?$")
_ADMIN_STATUSES = {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


async def fetch_bot_identity(token: str) -> TelegramUser | None:
    try:
        bot = Bot(token=token)
    except ValueError:
        return None

    try:
        return await bot.get_me()
    except TelegramAPIError:
        return None
    finally:
        await bot.session.close()


def extract_public_username(link: str) -> str | None:
    """Достаёт @username из публичной ссылки на канал/чат.

    Приватные пригласительные ссылки (t.me/+hash, t.me/joinchat/hash) намеренно не
    поддерживаются: у Bot API нет способа узнать chat_id по такой ссылке, пока бот не
    станет участником чата, а значит нет безопасного способа привязать её к конкретному
    заказу без риска перепутать чужие чаты.
    """
    link = link.strip()
    if "/+" in link or "/joinchat/" in link:
        return None
    match = _USERNAME_RE.match(link)
    if not match:
        return None
    return match.group(1)


async def resolve_admin_chat_id(check_bot_token: str, link: str) -> int | None:
    """Проверяет, что check-бот — администратор канала/чата по публичной ссылке.

    Возвращает chat_id при успехе, иначе None (ссылка не публичная, чат не найден или
    бот не добавлен в администраторы).
    """
    username = extract_public_username(link)
    if username is None:
        return None

    try:
        bot = Bot(token=check_bot_token)
    except ValueError:
        return None

    try:
        chat = await bot.get_chat(f"@{username}")
        member = await bot.get_chat_member(chat.id, bot.id)
        if member.status not in _ADMIN_STATUSES:
            return None
        return chat.id
    except TelegramAPIError:
        return None
    finally:
        await bot.session.close()
