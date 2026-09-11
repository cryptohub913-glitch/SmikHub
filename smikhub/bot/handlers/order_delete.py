from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import OrderDeleteCB
from smikhub.bot.handlers.order_panel import get_owned_order_or_alert
from smikhub.bot.keyboards import order_delete_confirm_kb, order_delete_success_kb, order_panel_kb
from smikhub.db import order_repo

router = Router(name="order_delete")


@router.callback_query(OrderDeleteCB.filter(F.action == "confirm"))
async def confirm_delete_order(
    callback: CallbackQuery, callback_data: OrderDeleteCB, session: AsyncSession
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await callback.message.edit_text(texts.DELETE_ORDER_CONFIRM, reply_markup=order_delete_confirm_kb(order))
    await callback.answer()


@router.callback_query(OrderDeleteCB.filter(F.action == "cancel"))
async def cancel_delete_order(
    callback: CallbackQuery, callback_data: OrderDeleteCB, session: AsyncSession
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await callback.message.edit_text(texts.order_panel(order), reply_markup=order_panel_kb(order))
    await callback.answer()


@router.callback_query(OrderDeleteCB.filter(F.action == "yes"))
async def delete_order(callback: CallbackQuery, callback_data: OrderDeleteCB, session: AsyncSession) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await order_repo.delete_order(session, order)
    await callback.message.edit_text(texts.DELETE_ORDER_SUCCESS, reply_markup=order_delete_success_kb())
    await callback.answer()
