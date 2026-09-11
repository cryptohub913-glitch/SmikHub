from decimal import Decimal

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import OrderPriceCB
from smikhub.bot.handlers.order_panel import get_owned_order_or_alert
from smikhub.bot.keyboards import order_panel_kb, order_price_grid_kb
from smikhub.db import order_repo, platform_repo

router = Router(name="order_price")


@router.callback_query(OrderPriceCB.filter(F.action == "show"))
async def show_order_price(
    callback: CallbackQuery, callback_data: OrderPriceCB, session: AsyncSession
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    settings = await platform_repo.get_platform_settings(session)
    await callback.message.edit_text(
        texts.order_price_screen(order), reply_markup=order_price_grid_kb(order, settings)
    )
    await callback.answer()


@router.callback_query(OrderPriceCB.filter(F.action == "set"))
async def set_order_price(callback: CallbackQuery, callback_data: OrderPriceCB, session: AsyncSession) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await order_repo.set_price(session, order, Decimal(callback_data.value))
    await callback.message.edit_text(texts.order_panel(order), reply_markup=order_panel_kb(order))
    await callback.answer()
