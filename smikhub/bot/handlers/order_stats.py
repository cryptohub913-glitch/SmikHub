from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import OrderStatsCB
from smikhub.bot.handlers.order_panel import get_owned_order_or_alert
from smikhub.bot.keyboards import order_stats_kb
from smikhub.db import order_repo

router = Router(name="order_stats")


@router.callback_query(OrderStatsCB.filter())
async def show_order_stats(callback: CallbackQuery, callback_data: OrderStatsCB, session: AsyncSession) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    stats = await order_repo.order_stats(session, order)
    await callback.message.edit_text(texts.order_stats_screen(order, stats), reply_markup=order_stats_kb(order))
    await callback.answer()
