from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import BuyApCB, MenuCB, OrderVerifyAdminCB
from smikhub.bot.keyboards import (
    buy_ap_cancel_kb,
    buy_ap_destination_kb,
    buy_ap_empty_kb,
    buy_ap_list_kb,
    buy_ap_traffic_kb,
    main_menu_kb,
    order_admin_kb,
    order_panel_kb,
)
from smikhub.bot.states import CreateOrderStates
from smikhub.config import get_settings
from smikhub.crypto import encrypt
from smikhub.db import order_repo, platform_repo, repo
from smikhub.db.models import DestinationType, TrafficType
from smikhub.services.telegram_client import extract_public_username, fetch_bot_identity, resolve_admin_chat_id

router = Router(name="buy_ap")


async def render_buy_ap_list(callback: CallbackQuery, session: AsyncSession) -> None:
    orders = await order_repo.list_user_orders(session, callback.from_user.id)
    if orders:
        await callback.message.edit_text(texts.BUY_AP_LIST_HEADER, reply_markup=buy_ap_list_kb(orders))
    else:
        await callback.message.edit_text(texts.BUY_AP_EMPTY, reply_markup=buy_ap_empty_kb())


@router.callback_query(MenuCB.filter(F.target == "buy_ap"))
async def show_buy_ap(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    platform_settings = await platform_repo.get_platform_settings(session)
    if not platform_settings.buy_ap_enabled:
        await callback.message.edit_text(texts.SECTION_DISABLED, reply_markup=main_menu_kb())
        await callback.answer()
        return

    await render_buy_ap_list(callback, session)
    await callback.answer()


@router.callback_query(BuyApCB.filter(F.step == "create"))
async def start_create_order(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(texts.BUY_AP_TRAFFIC_PROMPT, reply_markup=buy_ap_traffic_kb())
    await callback.answer()


@router.callback_query(BuyApCB.filter(F.step == "traffic"))
async def choose_traffic(callback: CallbackQuery, callback_data: BuyApCB, state: FSMContext) -> None:
    await state.update_data(traffic_type=callback_data.value)
    await callback.message.edit_text(
        texts.destination_prompt(callback_data.value), reply_markup=buy_ap_destination_kb()
    )
    await callback.answer()


@router.callback_query(BuyApCB.filter(F.step == "destination"))
async def choose_destination(callback: CallbackQuery, callback_data: BuyApCB, state: FSMContext) -> None:
    await state.update_data(destination_type=callback_data.value)
    await state.set_state(CreateOrderStates.waiting_for_destination_input)
    await callback.message.edit_text(
        texts.DESTINATION_LINK_PROMPTS[callback_data.value], reply_markup=buy_ap_cancel_kb()
    )
    await callback.answer()


@router.callback_query(BuyApCB.filter(F.step == "cancel"))
async def cancel_create_order(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await render_buy_ap_list(callback, session)
    await callback.answer()


@router.message(CreateOrderStates.waiting_for_destination_input)
async def receive_destination_input(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    traffic_type = data.get("traffic_type")
    destination_type = data.get("destination_type")
    text = (message.text or "").strip()

    if traffic_type is None or destination_type is None:
        await state.clear()
        return

    if destination_type == DestinationType.CHANNEL_CHAT.value:
        if extract_public_username(text) is None:
            await message.answer(texts.BUY_AP_INVALID_LINK, reply_markup=buy_ap_cancel_kb())
            return
        destination_link = text
    elif destination_type == DestinationType.BOT.value:
        identity = await fetch_bot_identity(text)
        if identity is None:
            await message.answer(texts.BUY_AP_INVALID_BOT_TOKEN, reply_markup=buy_ap_cancel_kb())
            return
        destination_link = encrypt(text)
    else:
        if not (text.startswith("http://") or text.startswith("https://")):
            await message.answer(texts.BUY_AP_INVALID_RESOURCE_LINK, reply_markup=buy_ap_cancel_kb())
            return
        destination_link = text

    user = await repo.get_or_create_user(session, message.from_user.id)
    platform_settings = await platform_repo.get_platform_settings(session)
    order = await order_repo.create_order(
        session,
        owner_id=user.id,
        traffic_type=TrafficType(traffic_type),
        destination_type=DestinationType(destination_type),
        destination_link=destination_link,
        default_price=Decimal(str(platform_settings.buy_price_grid_min)),
    )
    await state.clear()

    if destination_type == DestinationType.CHANNEL_CHAT.value:
        settings = get_settings()
        check_bot_identity = (
            await fetch_bot_identity(settings.check_bot_token) if settings.check_bot_token else None
        )
        if check_bot_identity is None:
            await message.answer(texts.ORDER_CHECK_BOT_NOT_CONFIGURED)
            await message.answer(texts.order_panel(order), reply_markup=order_panel_kb(order))
        else:
            await message.answer(
                texts.order_admin_prompt(check_bot_identity.username),
                reply_markup=order_admin_kb(order, check_bot_identity.username),
            )
    else:
        await message.answer(texts.order_panel(order), reply_markup=order_panel_kb(order))


@router.callback_query(OrderVerifyAdminCB.filter())
async def verify_admin(callback: CallbackQuery, callback_data: OrderVerifyAdminCB, session: AsyncSession) -> None:
    order = await order_repo.get_order(session, callback_data.order_id, owner_id=callback.from_user.id)
    if order is None:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    settings = get_settings()
    if settings.check_bot_token is None:
        await callback.answer(texts.ORDER_CHECK_BOT_NOT_CONFIGURED, show_alert=True)
        return

    chat_id = await resolve_admin_chat_id(settings.check_bot_token, order.destination_link)
    if chat_id is None:
        await callback.answer(texts.ORDER_ADMIN_NOT_CONFIRMED, show_alert=True)
        return

    await order_repo.set_target_chat(session, order, chat_id)
    await callback.message.edit_text(texts.order_panel(order), reply_markup=order_panel_kb(order))
    await callback.answer("Готово! Бот подтверждён администратором.")
