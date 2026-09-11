from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import TokenCB
from smikhub.bot.handlers.bot_panel import get_owned_bot_or_alert
from smikhub.bot.keyboards import token_kb
from smikhub.db import repo

router = Router(name="token")


@router.callback_query(TokenCB.filter())
async def show_integration_token(
    callback: CallbackQuery, callback_data: TokenCB, session: AsyncSession
) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    plain_token = repo.decrypt_integration_token(bot)
    await callback.message.edit_text(
        texts.integration_token_screen(bot, plain_token),
        reply_markup=token_kb(bot),
        parse_mode=ParseMode.MARKDOWN,
    )
    await callback.answer()
