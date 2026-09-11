from decimal import Decimal

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import PriceCB, SponsorsCB
from smikhub.bot.handlers.bot_panel import get_owned_bot_or_alert
from smikhub.bot.keyboards import bot_panel_kb, price_grid_kb, sponsors_grid_kb
from smikhub.db import platform_repo, repo

router = Router(name="pricing")


@router.callback_query(PriceCB.filter(F.action == "show"))
async def show_price_grid(callback: CallbackQuery, callback_data: PriceCB, session: AsyncSession) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    settings = await platform_repo.get_platform_settings(session)
    await callback.message.edit_text(texts.min_price_screen(bot), reply_markup=price_grid_kb(bot, settings))
    await callback.answer()


@router.callback_query(PriceCB.filter(F.action == "set"))
async def set_price(callback: CallbackQuery, callback_data: PriceCB, session: AsyncSession) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    await repo.set_min_price(session, bot, Decimal(callback_data.value))
    await callback.message.edit_text(texts.bot_panel(bot), reply_markup=bot_panel_kb(bot))
    await callback.answer()


@router.callback_query(SponsorsCB.filter(F.action == "show"))
async def show_sponsors_grid(
    callback: CallbackQuery, callback_data: SponsorsCB, session: AsyncSession
) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    settings = await platform_repo.get_platform_settings(session)
    await callback.message.edit_text(
        texts.max_sponsors_screen(bot), reply_markup=sponsors_grid_kb(bot, settings)
    )
    await callback.answer()


@router.callback_query(SponsorsCB.filter(F.action == "set"))
async def set_sponsors(callback: CallbackQuery, callback_data: SponsorsCB, session: AsyncSession) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    await repo.set_max_sponsors(session, bot, callback_data.value)
    await callback.message.edit_text(texts.bot_panel(bot), reply_markup=bot_panel_kb(bot))
    await callback.answer()
