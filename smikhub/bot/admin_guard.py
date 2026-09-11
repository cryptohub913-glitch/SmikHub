from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from smikhub.config import get_settings


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user.id in get_settings().admin_ids
