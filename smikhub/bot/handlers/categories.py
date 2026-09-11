from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import CategoryModeCB, DisabledCategoryCB
from smikhub.bot.handlers.bot_panel import get_owned_bot_or_alert
from smikhub.bot.keyboards import bot_panel_kb, category_mode_kb, disabled_categories_kb
from smikhub.db import repo
from smikhub.db.models import CategoryMode

router = Router(name="categories")


@router.callback_query(CategoryModeCB.filter(F.action == "show"))
async def show_category_mode(
    callback: CallbackQuery, callback_data: CategoryModeCB, session: AsyncSession
) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    await callback.message.edit_text(texts.category_mode_screen(bot), reply_markup=category_mode_kb(bot))
    await callback.answer()


@router.callback_query(CategoryModeCB.filter(F.action == "set"))
async def set_category_mode(
    callback: CallbackQuery, callback_data: CategoryModeCB, session: AsyncSession
) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    await repo.set_category_mode(session, bot, CategoryMode(callback_data.mode))
    await callback.message.edit_text(texts.bot_panel(bot), reply_markup=bot_panel_kb(bot))
    await callback.answer()


@router.callback_query(DisabledCategoryCB.filter(F.action == "show"))
async def show_disabled_categories(
    callback: CallbackQuery, callback_data: DisabledCategoryCB, session: AsyncSession
) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    categories = await repo.list_categories(session)
    await callback.message.edit_text(
        texts.disabled_categories_screen(bot), reply_markup=disabled_categories_kb(bot, categories)
    )
    await callback.answer()


@router.callback_query(DisabledCategoryCB.filter(F.action == "toggle"))
async def toggle_disabled_category(
    callback: CallbackQuery, callback_data: DisabledCategoryCB, session: AsyncSession
) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    await repo.toggle_disabled_category(session, bot, callback_data.category_id)
    categories = await repo.list_categories(session)
    await callback.message.edit_text(
        texts.disabled_categories_screen(bot), reply_markup=disabled_categories_kb(bot, categories)
    )
    await callback.answer()
