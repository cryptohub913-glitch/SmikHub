from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import PriorityCB
from smikhub.bot.handlers.bot_panel import get_owned_bot_or_alert
from smikhub.bot.keyboards import priority_kb
from smikhub.db import repo

router = Router(name="priority")


@router.callback_query(PriorityCB.filter(F.action == "show"))
async def show_priority(
    callback: CallbackQuery, callback_data: PriorityCB, session: AsyncSession
) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    await callback.message.edit_text(texts.priority_screen(bot), reply_markup=priority_kb(bot))
    await callback.answer()


@router.callback_query(PriorityCB.filter(F.action == "move"))
async def move_priority(
    callback: CallbackQuery, callback_data: PriorityCB, session: AsyncSession
) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    await repo.move_priority(session, bot, callback_data.provider, callback_data.direction)
    await callback.message.edit_text(texts.priority_screen(bot), reply_markup=priority_kb(bot))
    await callback.answer()
