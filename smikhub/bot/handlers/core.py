import secrets
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from smikhub.db.models import User, Bot, Order
from smikhub.bot.keyboards import main_menu_kb
from smikhub.config import BASE_URL

router = Router()

@router.message(CommandStart(deep_link=True))
@router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession, command: CommandObject = None):
    uid = message.from_user.id
    user = await session.get(User, uid)
    ref_id = None
    if command and command.args and command.args.startswith("ref_"):
        try:
            parsed = int(command.args.replace("ref_", ""))
            if parsed != uid:
                ref_id = parsed
        except ValueError:
            pass

    if not user:
        user = User(id=uid, username=message.from_user.username, referrer_id=ref_id)
        session.add(user)
        await session.commit()

    await message.answer(
        f"👋 **Добро пожаловать в SmikHub!**\nВаш баланс: **{float(user.balance or 0):.2f} RUB**",
        reply_markup=main_menu_kb(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "cabinet:referrals")
async def ref_cabinet(callback: types.CallbackQuery, session: AsyncSession):
    bot_me = await callback.bot.get_me()
    link = f"https://t.me/{bot_me.username}?start=ref_{callback.from_user.id}"
    await callback.message.edit_text(
        f"🤝 **Партнёрская программа SmikHub**\n\nПолучайте 5% с 1-й линии и 2% со 2-й линии доходов ботов!\n\n🔗 Ссылка: `{link}`",
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "cabinet:bots_list")
async def bots_list(callback: types.CallbackQuery, session: AsyncSession):
    bots = (await session.execute(select(Bot).where(Bot.user_id == callback.from_user.id))).scalars().all()
    if not bots:
        # Создаем тестового бота для быстрого старта, если ботов еще нет
        new_token = secrets.token_hex(16)
        b = Bot(user_id=callback.from_user.id, username="MyNewBot", integration_token=new_token)
        session.add(b)
        await session.commit()
        bots = [b]

    b = bots[0]
    snippet = f'''import aiohttp
SMIKHUB_URL = "{BASE_URL}"
AUTH_TOKEN = "{b.integration_token}"

async def get_sponsors(user_id: int):
    url = f"{SMIKHUB_URL}/api/v1/bot/sponsors"
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers={"Auth": AUTH_TOKEN}, params={"user_id": user_id}) as r:
            return await r.json() if r.status == 200 else []
'''
    text = f"🤖 **Управление ботом @{b.username}**\n\n🔑 Токен: `{b.integration_token}`\n\n🐍 **Пример кода:**\n```python\n{snippet}```"
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()
