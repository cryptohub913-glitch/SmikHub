from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import (
    OrderAgeCB,
    OrderCategoryCB,
    OrderCountryCB,
    OrderGenderCB,
    OrderLanguageCB,
    OrderPlacesCB,
    OrderPremiumCB,
)
from smikhub.bot.handlers.order_panel import get_owned_order_or_alert
from smikhub.bot.keyboards import (
    order_age_kb,
    order_categories_kb,
    order_countries_kb,
    order_gender_kb,
    order_languages_kb,
    order_panel_kb,
    order_places_kb,
    order_premium_kb,
)
from smikhub.db import order_repo, repo
from smikhub.db.models import AgeGroup, Gender, PremiumFilter

router = Router(name="order_targeting")


@router.callback_query(OrderCategoryCB.filter(F.action == "show"))
async def show_order_categories(
    callback: CallbackQuery, callback_data: OrderCategoryCB, session: AsyncSession
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    categories = await repo.list_categories(session)
    await callback.message.edit_text(
        texts.order_categories_screen(order), reply_markup=order_categories_kb(order, categories)
    )
    await callback.answer()


@router.callback_query(OrderCategoryCB.filter(F.action == "toggle"))
async def toggle_order_category(
    callback: CallbackQuery, callback_data: OrderCategoryCB, session: AsyncSession
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await order_repo.toggle_excluded_category(session, order, callback_data.category_id)
    categories = await repo.list_categories(session)
    await callback.message.edit_text(
        texts.order_categories_screen(order), reply_markup=order_categories_kb(order, categories)
    )
    await callback.answer()


@router.callback_query(OrderLanguageCB.filter(F.action == "show"))
async def show_order_languages(
    callback: CallbackQuery, callback_data: OrderLanguageCB, session: AsyncSession
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await callback.message.edit_text(texts.order_languages_screen(order), reply_markup=order_languages_kb(order))
    await callback.answer()


@router.callback_query(OrderLanguageCB.filter(F.action == "toggle"))
async def toggle_order_language(
    callback: CallbackQuery, callback_data: OrderLanguageCB, session: AsyncSession
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await order_repo.toggle_excluded_language(session, order, callback_data.code)
    await callback.message.edit_text(texts.order_languages_screen(order), reply_markup=order_languages_kb(order))
    await callback.answer()


@router.callback_query(OrderCountryCB.filter(F.action == "show"))
async def show_order_countries(
    callback: CallbackQuery, callback_data: OrderCountryCB, session: AsyncSession
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await callback.message.edit_text(texts.order_countries_screen(order), reply_markup=order_countries_kb(order))
    await callback.answer()


@router.callback_query(OrderCountryCB.filter(F.action == "toggle"))
async def toggle_order_country(
    callback: CallbackQuery, callback_data: OrderCountryCB, session: AsyncSession
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await order_repo.toggle_excluded_country(session, order, callback_data.code)
    await callback.message.edit_text(texts.order_countries_screen(order), reply_markup=order_countries_kb(order))
    await callback.answer()


@router.callback_query(OrderGenderCB.filter(F.action == "show"))
async def show_order_gender(
    callback: CallbackQuery, callback_data: OrderGenderCB, session: AsyncSession
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await callback.message.edit_text(texts.order_gender_screen(order), reply_markup=order_gender_kb(order))
    await callback.answer()


@router.callback_query(OrderGenderCB.filter(F.action == "set"))
async def set_order_gender(callback: CallbackQuery, callback_data: OrderGenderCB, session: AsyncSession) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await order_repo.set_gender(session, order, Gender(callback_data.value))
    await callback.message.edit_text(texts.order_panel(order), reply_markup=order_panel_kb(order))
    await callback.answer()


@router.callback_query(OrderAgeCB.filter(F.action == "show"))
async def show_order_age(callback: CallbackQuery, callback_data: OrderAgeCB, session: AsyncSession) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await callback.message.edit_text(texts.order_age_screen(order), reply_markup=order_age_kb(order))
    await callback.answer()


@router.callback_query(OrderAgeCB.filter(F.action == "set"))
async def set_order_age(callback: CallbackQuery, callback_data: OrderAgeCB, session: AsyncSession) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await order_repo.set_age_group(session, order, AgeGroup(callback_data.value))
    await callback.message.edit_text(texts.order_panel(order), reply_markup=order_panel_kb(order))
    await callback.answer()


@router.callback_query(OrderPremiumCB.filter(F.action == "show"))
async def show_order_premium(
    callback: CallbackQuery, callback_data: OrderPremiumCB, session: AsyncSession
) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await callback.message.edit_text(texts.order_premium_screen(order), reply_markup=order_premium_kb(order))
    await callback.answer()


@router.callback_query(OrderPremiumCB.filter(F.action == "set"))
async def set_order_premium(callback: CallbackQuery, callback_data: OrderPremiumCB, session: AsyncSession) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await order_repo.set_premium_filter(session, order, PremiumFilter(callback_data.value))
    await callback.message.edit_text(texts.order_panel(order), reply_markup=order_panel_kb(order))
    await callback.answer()


@router.callback_query(OrderPlacesCB.filter())
async def show_order_places(callback: CallbackQuery, callback_data: OrderPlacesCB, session: AsyncSession) -> None:
    order = await get_owned_order_or_alert(callback, session, callback_data.order_id)
    if order is None:
        return
    await callback.message.edit_text(texts.ORDER_PLACES, reply_markup=order_places_kb(order))
    await callback.answer()
