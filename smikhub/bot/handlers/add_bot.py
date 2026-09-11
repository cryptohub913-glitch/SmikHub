from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import AddBotCB, MenuCB
from smikhub.bot.keyboards import (
    add_bot_method_kb,
    add_bot_token_kb,
    bot_panel_kb,
    main_menu_kb,
    sell_ap_empty_kb,
    sell_ap_list_kb,
)
from smikhub.bot.states import AddBotStates
from smikhub.db import platform_repo, repo
from smikhub.services.telegram_client import fetch_bot_identity

router = Router(name="add_bot")


@router.callback_query(MenuCB.filter(F.target == "sell_ap"))
async def show_sell_ap(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    platform_settings = await platform_repo.get_platform_settings(session)
    if not platform_settings.sell_ap_enabled:
        await callback.message.edit_text(texts.SECTION_DISABLED, reply_markup=main_menu_kb())
        await callback.answer()
        return

    bots = await repo.list_user_bots(session, callback.from_user.id)
    if bots:
        await callback.message.edit_text(texts.SELL_AP_LIST_HEADER, reply_markup=sell_ap_list_kb(bots))
    else:
        await callback.message.edit_text(texts.SELL_AP_EMPTY, reply_markup=sell_ap_empty_kb())
    await callback.answer()


@router.callback_query(AddBotCB.filter(F.action == "method"))
async def show_add_bot_method(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(texts.ADD_BOT_METHOD, reply_markup=add_bot_method_kb())
    await callback.answer()


@router.callback_query(AddBotCB.filter(F.action == "token"))
async def request_bot_token(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddBotStates.waiting_for_token)
    await callback.message.edit_text(
        texts.ADD_BOT_TOKEN_PROMPT, reply_markup=add_bot_token_kb(), parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


@router.callback_query(AddBotCB.filter(F.action == "cancel"))
async def cancel_add_bot(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(texts.ADD_BOT_METHOD, reply_markup=add_bot_method_kb())
    await callback.answer()


@router.message(StateFilter(AddBotStates.waiting_for_token))
async def receive_bot_token(message: Message, session: AsyncSession, state: FSMContext) -> None:
    token = (message.text or "").strip()
    identity = await fetch_bot_identity(token) if token else None
    if identity is None:
        await message.answer(texts.ADD_BOT_INVALID_TOKEN, reply_markup=add_bot_token_kb())
        return

    existing = await repo.get_bot_by_telegram_id(session, identity.id)
    if existing is not None:
        await message.answer(texts.ADD_BOT_ALREADY_EXISTS, reply_markup=add_bot_token_kb())
        return

    user = await repo.get_or_create_user(session, message.from_user.id)
    platform_settings = await platform_repo.get_platform_settings(session)
    bot = await repo.create_bot(
        session,
        owner_id=user.id,
        telegram_bot_id=identity.id,
        username=identity.username or str(identity.id),
        bot_token=token,
        default_min_price=platform_settings.sell_default_min_price,
        default_max_sponsors=platform_settings.sell_default_max_sponsors,
    )
    await state.clear()
    await message.answer(texts.bot_panel(bot), reply_markup=bot_panel_kb(bot))
