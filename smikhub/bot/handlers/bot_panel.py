from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import BotCB
from smikhub.bot.keyboards import bot_panel_kb, sell_ap_empty_kb, sell_ap_list_kb
from smikhub.db import repo
from smikhub.db.models import ManagedBot

router = Router(name="bot_panel")


async def get_owned_bot_or_alert(
    callback: CallbackQuery, session: AsyncSession, bot_id: int
) -> ManagedBot | None:
    bot = await repo.get_bot(session, bot_id, owner_id=callback.from_user.id)
    if bot is None:
        await callback.answer("Бот не найден", show_alert=True)
    return bot


@router.callback_query(BotCB.filter(F.action.in_({"open", "refresh"})))
async def open_bot_panel(
    callback: CallbackQuery, callback_data: BotCB, session: AsyncSession, state: FSMContext
) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    await state.clear()
    await callback.message.edit_text(texts.bot_panel(bot), reply_markup=bot_panel_kb(bot))
    await callback.answer()


@router.callback_query(BotCB.filter(F.action == "toggle_active"))
async def toggle_bot_active(callback: CallbackQuery, callback_data: BotCB, session: AsyncSession) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    await repo.toggle_active(session, bot)
    await callback.message.edit_text(texts.bot_panel(bot), reply_markup=bot_panel_kb(bot))
    await callback.answer()


@router.callback_query(BotCB.filter(F.action == "back"))
async def back_to_sell_ap(callback: CallbackQuery, session: AsyncSession) -> None:
    bots = await repo.list_user_bots(session, callback.from_user.id)
    if bots:
        await callback.message.edit_text(texts.SELL_AP_LIST_HEADER, reply_markup=sell_ap_list_kb(bots))
    else:
        await callback.message.edit_text(texts.SELL_AP_EMPTY, reply_markup=sell_ap_empty_kb())
    await callback.answer()
