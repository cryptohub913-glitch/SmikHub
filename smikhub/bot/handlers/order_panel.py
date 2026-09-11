from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import OrderCB
from smikhub.bot.handlers.buy_ap import render_buy_ap_list
from smikhub.bot.keyboards import order_panel_kb
from smikhub.db import order_repo
from smikhub.db.models import Order

router = Router(name="order_panel")


async def get_owned_order_or_alert(
    callback: CallbackQuery, session: AsyncSession, order_id: int
) -> Order | None:
    order = await order_repo.get_order(session, order_id, owner_id=callback.from_user.id)
    if order is None:
        await callback.answer("Заказ не найден", show_alert=True)
    return order


@router.callback_query(OrderCB.filter(F.action.in_({"open", "refresh"})))
async def open_order_panel(
    callback: CallbackQuery, callback_data: OrderCB, session: AsyncSession, state: FSMContext
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await state.clear()
    await callback.message.edit_text(texts.order_panel(order), reply_markup=order_panel_kb(order))
    await callback.answer()


@router.callback_query(OrderCB.filter(F.action == "toggle_status"))
async def toggle_order_status(callback: CallbackQuery, callback_data: OrderCB, session: AsyncSession) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await order_repo.toggle_status(session, order)
    await callback.message.edit_text(texts.order_panel(order), reply_markup=order_panel_kb(order))
    await callback.answer()


@router.callback_query(OrderCB.filter(F.action == "back"))
async def back_to_buy_ap(callback: CallbackQuery, session: AsyncSession) -> None:
    await render_buy_ap_list(callback, session)
    await callback.answer()
