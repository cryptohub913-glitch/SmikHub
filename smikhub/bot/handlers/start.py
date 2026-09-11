from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import MenuCB
from smikhub.bot.keyboards import main_menu_kb
from smikhub.db import repo

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    await repo.get_or_create_user(session, message.from_user.id)
    await message.answer(texts.MAIN_MENU, reply_markup=main_menu_kb())


@router.callback_query(MenuCB.filter(F.target == "main"))
async def show_main_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(texts.MAIN_MENU, reply_markup=main_menu_kb())
    await callback.answer()
