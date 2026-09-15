import secrets
from decimal import Decimal
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.db.models import User, Bot, Order
from smikhub.bot.keyboards import (
    main_menu_kb,
    cabinet_kb,
    topup_methods_kb,
    withdraw_methods_kb,
    back_kb
)

router = Router()


# -------------------------------------------------------------
# Главное меню и /start
# -------------------------------------------------------------
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

    text = (
        "👋 **Добро пожаловать в SmikHub!**\n\n"
        "Платформа монетизации и закупки обязательных подписок (ОП) в Telegram.\n"
        "Управляйте балансом, подключайте ботов и запускайте рекламу через меню ниже."
    )
    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "nav:main_menu")
async def nav_main_menu(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "👋 **Главное меню SmikHub**\n\n"
        "Выберите интересующий раздел:"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb(), parse_mode="Markdown")


# -------------------------------------------------------------
# Кабинет пользователя (Пополнить / Вывести)
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:cabinet")
async def nav_cabinet(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    text = (
        f"👤 **Личный кабинет**\n\n"
        f"🆔 Ваш Telegram ID: `{callback.from_user.id}`\n"
        f"💰 Баланс аккаунта: **{balance:.2f} RUB**\n\n"
        f"Выберите действие для работы со счётом:"
    )
    await callback.message.edit_text(text, reply_markup=cabinet_kb(), parse_mode="Markdown")


# Раздел Пополнить
@router.callback_query(F.data == "nav:topup_menu")
async def nav_topup_menu(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "💳 **Пополнение баланса**\n\n"
        "Выберите удобный платёжный шлюз:"
    )
    await callback.message.edit_text(text, reply_markup=topup_methods_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "topup:cryptobot")
async def topup_cryptobot(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "🤖 **Пополнение через CryptoBot**\n\n"
        "Шлюз принимает USDT, TON, BTC, NOT.\n"
        "Оплата зачисляется моментально после подтверждения транзакции в сети."
    )
    await callback.message.edit_text(text, reply_markup=back_kb(target="topup_menu"), parse_mode="Markdown")


@router.callback_query(F.data == "topup:stars")
async def topup_stars(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "⭐️ **Пополнение через Telegram Stars**\n\n"
        "Нативная оплата внутри Telegram с баланса Stars.\n"
        "Курс конвертации: 1 Star ≈ 1.50 RUB."
    )
    await callback.message.edit_text(text, reply_markup=back_kb(target="topup_menu"), parse_mode="Markdown")


# Раздел Вывести
@router.callback_query(F.data == "nav:withdraw_menu")
async def nav_withdraw_menu(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    text = (
        f"📤 **Вывод средств**\n\n"
        f"Доступно к выводу: **{balance:.2f} RUB**\n"
        f"Минимальная сумма заявки: **100.00 RUB**\n\n"
        f"Доступные шлюзы для вывода:"
    )
    await callback.message.edit_text(text, reply_markup=withdraw_methods_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "withdraw:sendpay")
async def withdraw_sendpay(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    if balance < 100.0:
        text = (
            "⚠️ **Недостаточно средств для вывода**\n\n"
            f"Текущий баланс: **{balance:.2f} RUB**\n"
            "Минимальный порог выплаты через SendPay: **100.00 RUB**."
        )
    else:
        text = (
            "💳 **Выплата через шлюз SendPay (Карты / СБП)**\n\n"
            "Заявка отправляется в автоматический процессинг SendPay.\n"
            "Средства поступают на карту РФ или СБП в течение 10–15 минут."
        )
    await callback.message.edit_text(text, reply_markup=back_kb(target="withdraw_menu"), parse_mode="Markdown")


# -------------------------------------------------------------
# Добавить бота
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:add_bot")
async def nav_add_bot(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    new_token = secrets.token_hex(16)
    new_bot = Bot(
        user_id=callback.from_user.id,
        username=f"Bot_{callback.from_user.id % 10000}",
        integration_token=new_token,
        min_price=Decimal("0.50"),
        max_sponsors=3
    )
    session.add(new_bot)
    await session.commit()

    text = (
        f"✅ **Бот успешно подключён!**\n\n"
        f"🔑 Ваш токен API: `{new_token}`\n\n"
        f"Вставьте этот токен в заголовок `Auth` при запросе к `/api/v1/bot/sponsors`, "
        f"чтобы получать оплачиваемых спонсоров в вашего бота."
    )
    await callback.message.edit_text(text, reply_markup=back_kb(target="main_menu"), parse_mode="Markdown")


# -------------------------------------------------------------
# Продать ОП
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:sell_traffic")
async def nav_sell_traffic(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bots = (await session.execute(
        select(Bot).where(Bot.user_id == callback.from_user.id)
    )).scalars().all()

    if not bots:
        text = (
            "🤖 **Продажа ОП (Монетизация)**\n\n"
            "У вас ещё нет добавленных ботов.\n"
            "Нажмите кнопку «➕ Добавить бота» в меню, чтобы сгенерировать токен."
        )
    else:
        items = "\n".join([f"• @{b.username} | Статус: Активен | Токен: `{b.integration_token[:8]}...`" for b in bots])
        text = (
            f"🤖 **Ваши боты в сети SmikHub:**\n\n{items}\n\n"
            "За каждую выполненную подписку вашими пользователями баланс пополняется автоматически."
        )
    await callback.message.edit_text(text, reply_markup=back_kb(target="main_menu"), parse_mode="Markdown")


# -------------------------------------------------------------
# Купить ОП
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:buy_traffic")
async def nav_buy_traffic(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    orders = (await session.execute(
        select(Order).where(Order.user_id == callback.from_user.id)
    )).scalars().all()

    if not orders:
        text = (
            "📢 **Покупка ОП (Реклама)**\n\n"
            "У вас пока нет активных рекламных кампаний.\n"
            "Пополните баланс в Кабинете, чтобы запустить закупку целевых подписчиков на канал."
        )
    else:
        items = "\n".join([f"• Заказ #{o.id} | Остаток бюджета: {float(o.remaining_budget):.2f} RUB | Статус: {o.status}" for o in orders])
        text = f"📢 **Ваши рекламные кампании:**\n\n{items}"

    await callback.message.edit_text(text, reply_markup=back_kb(target="main_menu"), parse_mode="Markdown")


# -------------------------------------------------------------
# Партнёрка
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:referrals")
async def nav_referrals(callback: types.CallbackQuery):
    await callback.answer()
    bot_me = await callback.bot.get_me()
    link = f"https://t.me/{bot_me.username}?start=ref_{callback.from_user.id}"
    text = (
        "🤝 **Партнёрская программа SmikHub**\n\n"
        "Приглашайте владельцев ботов и рекламодателей:\n"
        "• **5%** от дохода ботов 1-го уровня\n"
        "• **2%** от дохода ботов 2-го уровня\n\n"
        f"🔗 Ваша реферальная ссылка:\n`{link}`"
    )
    await callback.message.edit_text(text, reply_markup=back_kb(target="main_menu"), parse_mode="Markdown")