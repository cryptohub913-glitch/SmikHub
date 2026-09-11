from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import OrderLogCB
from smikhub.bot.handlers.order_panel import get_owned_order_or_alert
from smikhub.bot.keyboards import order_log_kb
from smikhub.db import order_repo

router = Router(name="order_log")


@router.callback_query(OrderLogCB.filter())
async def show_order_log(callback: CallbackQuery, callback_data: OrderLogCB, session: AsyncSession) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return

    events = await order_repo.list_recent_join_events(session, order)
    quality_pct, non_quality_pct = await order_repo.quality_ratio(session, order)
    await callback.message.edit_text(
        texts.order_log_screen(order, events, quality_pct, non_quality_pct),
        reply_markup=order_log_kb(order),
    )
    await callback.answer()
