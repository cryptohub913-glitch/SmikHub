from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import DeleteCB
from smikhub.bot.handlers.bot_panel import get_owned_bot_or_alert
from smikhub.bot.keyboards import bot_panel_kb, delete_confirm_kb, delete_success_kb
from smikhub.db import repo

router = Router(name="delete")


@router.callback_query(DeleteCB.filter(F.action == "confirm"))
async def confirm_delete(callback: CallbackQuery, callback_data: DeleteCB, session: AsyncSession) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    await callback.message.edit_text(texts.DELETE_CONFIRM, reply_markup=delete_confirm_kb(bot))
    await callback.answer()


@router.callback_query(DeleteCB.filter(F.action == "cancel"))
async def cancel_delete(callback: CallbackQuery, callback_data: DeleteCB, session: AsyncSession) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    await callback.message.edit_text(texts.bot_panel(bot), reply_markup=bot_panel_kb(bot))
    await callback.answer()


@router.callback_query(DeleteCB.filter(F.action == "yes"))
async def delete_bot(callback: CallbackQuery, callback_data: DeleteCB, session: AsyncSession) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    await repo.delete_bot(session, bot)
    await callback.message.edit_text(texts.DELETE_SUCCESS, reply_markup=delete_success_kb())
    await callback.answer()
