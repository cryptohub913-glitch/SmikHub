from collections.abc import Awaitable, Callable

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import OrderSettingsCB
from smikhub.bot.handlers.order_panel import get_owned_order_or_alert
from smikhub.bot.keyboards import order_cancel_kb, order_settings_kb
from smikhub.bot.states import OrderSettingsStates
from smikhub.crypto import encrypt
from smikhub.db import order_repo
from smikhub.db.models import DestinationType, Order
from smikhub.services.telegram_client import extract_public_username, fetch_bot_identity

router = Router(name="order_settings")


@router.callback_query(OrderSettingsCB.filter(F.action == "show"))
async def show_order_settings(
    callback: CallbackQuery, callback_data: OrderSettingsCB, session: AsyncSession
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await callback.message.edit_text(texts.order_settings_screen(order), reply_markup=order_settings_kb(order))
    await callback.answer()


@router.callback_query(OrderSettingsCB.filter(F.action == "toggle_distribute"))
async def toggle_distribute(
    callback: CallbackQuery, callback_data: OrderSettingsCB, session: AsyncSession
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await order_repo.toggle_distribute_during_day(session, order)
    await callback.message.edit_text(texts.order_settings_screen(order), reply_markup=order_settings_kb(order))
    await callback.answer()


@router.callback_query(OrderSettingsCB.filter(F.action == "change_link"))
async def request_new_link(callback: CallbackQuery, callback_data: OrderSettingsCB, state: FSMContext) -> None:
    await state.set_state(OrderSettingsStates.waiting_for_new_link)
    await state.update_data(order_id=callback_data.order_id)
    await callback.message.edit_text(
        texts.ORDER_SETTINGS_LINK_PROMPT, reply_markup=order_cancel_kb(callback_data.order_id)
    )
    await callback.answer()


@router.callback_query(OrderSettingsCB.filter(F.action == "per_day"))
async def request_users_per_day(
    callback: CallbackQuery, callback_data: OrderSettingsCB, state: FSMContext
) -> None:
    await state.set_state(OrderSettingsStates.waiting_for_users_per_day)
    await state.update_data(order_id=callback_data.order_id)
    await callback.message.edit_text(
        texts.ORDER_SETTINGS_USERS_PER_DAY_PROMPT, reply_markup=order_cancel_kb(callback_data.order_id)
    )
    await callback.answer()


@router.callback_query(OrderSettingsCB.filter(F.action == "total"))
async def request_users_total(
    callback: CallbackQuery, callback_data: OrderSettingsCB, state: FSMContext
) -> None:
    await state.set_state(OrderSettingsStates.waiting_for_users_total)
    await state.update_data(order_id=callback_data.order_id)
    await callback.message.edit_text(
        texts.ORDER_SETTINGS_USERS_TOTAL_PROMPT, reply_markup=order_cancel_kb(callback_data.order_id)
    )
    await callback.answer()


async def _get_order_from_state(
    message: Message, session: AsyncSession, state: FSMContext
) -> Order | None:
    data = await state.get_data()
    order_id = data.get("order_id")
    if order_id is None:
        await state.clear()
        return None
    order = await order_repo.get_order(session, order_id, owner_id=message.from_user.id)
    if order is None:
        await state.clear()
    return order


@router.message(OrderSettingsStates.waiting_for_new_link)
async def receive_new_link(message: Message, session: AsyncSession, state: FSMContext) -> None:
    order = await _get_order_from_state(message, session, state)
    if order is None:
        return

    text = (message.text or "").strip()
    cancel_kb = order_cancel_kb(order.id)
    if order.destination_type == DestinationType.CHANNEL_CHAT:
        if extract_public_username(text) is None:
            await message.answer(texts.BUY_AP_INVALID_LINK, reply_markup=cancel_kb)
            return
        new_link = text
    elif order.destination_type == DestinationType.BOT:
        identity = await fetch_bot_identity(text)
        if identity is None:
            await message.answer(texts.BUY_AP_INVALID_BOT_TOKEN, reply_markup=cancel_kb)
            return
        new_link = encrypt(text)
    else:
        if not (text.startswith("http://") or text.startswith("https://")):
            await message.answer(texts.BUY_AP_INVALID_RESOURCE_LINK, reply_markup=cancel_kb)
            return
        new_link = text

    await order_repo.set_destination_link(session, order, new_link)
    await state.clear()
    await message.answer(texts.order_settings_screen(order), reply_markup=order_settings_kb(order))


async def _receive_limit(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    setter: Callable[[AsyncSession, Order, int | None], Awaitable[None]],
) -> None:
    order = await _get_order_from_state(message, session, state)
    if order is None:
        return

    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(texts.ORDER_SETTINGS_INVALID_NUMBER, reply_markup=order_cancel_kb(order.id))
        return

    value = int(text)
    await setter(session, order, value if value > 0 else None)
    await state.clear()
    await message.answer(texts.order_settings_screen(order), reply_markup=order_settings_kb(order))


@router.message(OrderSettingsStates.waiting_for_users_per_day)
async def receive_users_per_day(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _receive_limit(message, session, state, order_repo.set_users_per_day)


@router.message(OrderSettingsStates.waiting_for_users_total)
async def receive_users_total(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _receive_limit(message, session, state, order_repo.set_users_total)
