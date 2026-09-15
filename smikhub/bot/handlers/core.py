import secrets
from decimal import Decimal
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.db.models import User, Bot, Order
from smikhub.config import BASE_URL, ADMIN_CHAT_ID
from smikhub.bot.keyboards import (
    main_menu_kb,
    cabinet_kb,
    topup_methods_kb,
    withdraw_methods_kb,
    bot_list_kb,
    bot_settings_kb,
    buy_traffic_kb,
    back_kb
)

router = Router()


class CampaignStates(StatesGroup):
    waiting_for_budget = State()
    waiting_for_price = State()


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
        "Биржа обязательных подписок (ОП) в Telegram.\n"
        "Используйте кнопки ниже для управления кабинетом, ботами и рекламой."
    )
    
    kb = main_menu_kb()
    if uid == ADMIN_CHAT_ID:
        kb.inline_keyboard.append([types.InlineKeyboardButton(text="🛠 Админ-панель", callback_data="nav:admin")])

    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "nav:main_menu")
async def nav_main_menu(callback: types.CallbackQuery):
    await callback.answer()
    kb = main_menu_kb()
    if callback.from_user.id == ADMIN_CHAT_ID:
        kb.inline_keyboard.append([types.InlineKeyboardButton(text="🛠 Админ-панель", callback_data="nav:admin")])

    text = "👋 **Главное меню SmikHub**\n\nВыберите нужный раздел:"
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


# -------------------------------------------------------------
# Админ-панель
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:admin")
async def nav_admin(callback: types.CallbackQuery, session: AsyncSession):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("Доступ запрещен.", show_alert=True)
        return
    await callback.answer()

    users_count = len((await session.execute(select(User))).scalars().all())
    bots_count = len((await session.execute(select(Bot))).scalars().all())
    orders_count = len((await session.execute(select(Order))).scalars().all())

    text = (
        "🛠 **Административная панель SmikHub**\n\n"
        f"👥 Всего пользователей: `{users_count}`\n"
        f"🤖 Всего ботов: `{bots_count}`\n"
        f"📢 Всего заказов: `{orders_count}`"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="admin:broadcast")],
        [types.InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        return
    await callback.answer()
    await callback.message.edit_text(
        "📢 **Рассылка сообщений**\n\nОтправьте текст для рассылки всем пользователям бота.",
        reply_markup=back_kb(target="admin")
    )


# -------------------------------------------------------------
# Кабинет пользователя
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:cabinet")
async def nav_cabinet(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    text = (
        f"👤 **Личный кабинет**\n\n"
        f"🆔 Ваш ID: `{callback.from_user.id}`\n"
        f"💰 Баланс: **{balance:.2f} RUB**\n\n"
        f"Выберите действие со счётом:"
    )
    await callback.message.edit_text(text, reply_markup=cabinet_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "nav:topup_menu")
async def nav_topup_menu(callback: types.CallbackQuery):
    await callback.answer()
    text = "💳 **Выберите способ пополнения баланса:**"
    await callback.message.edit_text(text, reply_markup=topup_methods_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "topup:cryptobot")
async def topup_cryptobot(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "🤖 **Пополнение через CryptoBot**\n\n"
        "Поддерживаемые криптовалюты: USDT, TON, BTC, NOT.\n"
        "Баланс зачисляется автоматически после оплаты счета."
    )
    await callback.message.edit_text(text, reply_markup=back_kb(target="topup_menu"), parse_mode="Markdown")


@router.callback_query(F.data == "topup:stars")
async def topup_stars(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "⭐️ **Пополнение через Telegram Stars**\n\n"
        "Оплата звёздами нативно в интерфейсе Telegram.\n"
        "Курс конвертации: 1 Star = 1.50 RUB."
    )
    await callback.message.edit_text(text, reply_markup=back_kb(target="topup_menu"), parse_mode="Markdown")


@router.callback_query(F.data == "nav:withdraw_menu")
async def nav_withdraw_menu(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    text = (
        f"📤 **Вывод средств**\n\n"
        f"Доступно: **{balance:.2f} RUB**\n"
        f"Минимальная сумма: **100.00 RUB**"
    )
    await callback.message.edit_text(text, reply_markup=withdraw_methods_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "withdraw:sendpay")
async def withdraw_sendpay(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    if balance < 100.0:
        text = (
            "⚠️ **Недостаточно средств**\n\n"
            f"Текущий баланс: **{balance:.2f} RUB**.\n"
            "Минимум для вывода через SendPay — 100.00 RUB."
        )
    else:
        text = (
            "💳 **Вывод через SendPay (СБП / Карты)**\n\n"
            "Заявка сформирована и передана на выплату."
        )
    await callback.message.edit_text(text, reply_markup=back_kb(target="withdraw_menu"), parse_mode="Markdown")


# -------------------------------------------------------------
# Добавить бота
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:add_bot")
async def nav_add_bot(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    new_token = secrets.token_hex(16)
    bot_num = callback.from_user.id % 10000
    new_bot = Bot(
        user_id=callback.from_user.id,
        username=f"Bot_{bot_num}",
        integration_token=new_token,
        min_price=Decimal("0.50"),
        max_sponsors=3
    )
    session.add(new_bot)
    await session.commit()

    text = (
        f"✅ **Бот успешно добавлен в систему!**\n\n"
        f"• Имя: `@{new_bot.username}`\n"
        f"• Токен: `{new_token}`\n\n"
        "Перейдите в раздел «Продать ОП», чтобы настроить параметры."
    )
    await callback.message.edit_text(text, reply_markup=back_kb(target="sell_traffic"), parse_mode="Markdown")


# -------------------------------------------------------------
# Продать ОП (Настройки ботов)
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:sell_traffic")
async def nav_sell_traffic(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bots = (await session.execute(
        select(Bot).where(Bot.user_id == callback.from_user.id)
    )).scalars().all()

    if not bots:
        text = (
            "🤖 **Монетизация (Продажа ОП)**\n\n"
            "У вас нет добавленных ботов. Нажмите кнопку ниже, чтобы подключить первого бота."
        )
        await callback.message.edit_text(text, reply_markup=bot_list_kb([]), parse_mode="Markdown")
        return

    text = "🤖 **Ваши подключенные боты:**\n\nВыберите бота для настройки:"
    await callback.message.edit_text(text, reply_markup=bot_list_kb(bots), parse_mode="Markdown")


@router.callback_query(F.data.startswith("bot_manage:"))
async def bot_manage(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)

    if not bot_obj:
        await callback.message.edit_text("Бот не найден.", reply_markup=back_kb(target="sell_traffic"))
        return

    text = (
        f"⚙️ **Управление ботом @{bot_obj.username}**\n\n"
        f"• Мин. цена: **{float(bot_obj.min_price):.2f} RUB**\n"
        f"• Способов/Спонсоров: **{bot_obj.max_sponsors}**\n"
        f"• Рейтинг: **{bot_obj.quality_score * 100:.0f}%**\n\n"
        "Настройте параметры кнопками ниже:"
    )
    await callback.message.edit_text(text, reply_markup=bot_settings_kb(bot_id), parse_mode="Markdown")


@router.callback_query(F.data.startswith("bot_show_token:"))
async def bot_show_token(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    text = f"🔑 **Токен интеграции:**\n\n`{bot_obj.integration_token}`"
    await callback.message.edit_text(text, reply_markup=back_kb(target=f"sell_traffic"), parse_mode="Markdown")


@router.callback_query(F.data.startswith("bot_code_snippet:"))
async def bot_code_snippet(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)

    code = (
        "```python\n"
        "import requests\n\n"
        f"url = '{BASE_URL}/api/v1/bot/sponsors'\n"
        f"headers = {{'Authorization': 'Bearer {bot_obj.integration_token}'}}\n"
        "params = {'user_id': message.from_user.id}\n"
        "response = requests.get(url, headers=headers, params=params).json()\n"
        "```"
    )
    await callback.message.edit_text(f"📋 **Пример кода для интеграции:**\n\n{code}", reply_markup=back_kb(target=f"sell_traffic"), parse_mode="Markdown")


@router.callback_query(F.data.startswith("bot_edit_price:"))
async def bot_edit_price(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    current = float(bot_obj.min_price)
    next_price = 1.00 if current == 0.50 else (1.50 if current == 1.00 else (2.00 if current == 1.50 else 0.50))
    bot_obj.min_price = Decimal(str(next_price))
    await session.commit()
    await bot_manage(callback, session)


@router.callback_query(F.data.startswith("bot_edit_sponsors:"))
async def bot_edit_sponsors(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    bot_obj.max_sponsors = 1 if bot_obj.max_sponsors >= 5 else (bot_obj.max_sponsors + 1)
    await session.commit()
    await bot_manage(callback, session)


@router.callback_query(F.data.startswith("bot_delete:"))
async def bot_delete(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        await session.delete(bot_obj)
        await session.commit()
    await callback.message.edit_text("🗑 **Бот удален.**", reply_markup=back_kb(target="sell_traffic"), parse_mode="Markdown")


# -------------------------------------------------------------
# Купить ОП (Создание и управление кампаниями)
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:buy_traffic")
async def nav_buy_traffic(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    orders = (await session.execute(
        select(Order).where(Order.user_id == callback.from_user.id)
    )).scalars().all()

    text = (
        "📢 **Закупка трафика (Купить ОП)**\n\n"
        "Создавайте рекламные кампании для привлечения подписчиков."
    )
    await callback.message.edit_text(text, reply_markup=buy_traffic_kb(orders), parse_mode="Markdown")


@router.callback_query(F.data == "nav:create_order")
async def nav_create_order(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    if balance < 100.0:
        text = (
            "⚠️ **Недостаточно средств**\n\n"
            f"Баланс: **{balance:.2f} RUB** (мин. бюджет кампании — 100 RUB).\n"
            "Пополните баланс в Кабинете."
        )
        await callback.message.edit_text(text, reply_markup=back_kb(target="buy_traffic"), parse_mode="Markdown")
        return

    await state.set_state(CampaignStates.waiting_for_budget)
    text = "✍️ **Введите общий бюджет рекламной кампании в рублях (например, 500):**"
    await callback.message.edit_text(text, reply_markup=back_kb(target="buy_traffic"), parse_mode="Markdown")


@router.message(CampaignStates.waiting_for_budget)
async def process_budget(message: types.Message, state: FSMContext):
    try:
        budget = float(message.text.strip())
        if budget < 100:
            raise ValueError()
        await state.update_data(budget=budget)
        await state.set_state(CampaignStates.waiting_for_price)
        await message.answer("✍️ **Введите цену за 1 подписчика (CPC) в рублях (например, 1.20):**")
    except ValueError:
        await message.answer("⚠️ Введите корректное число (не менее 100):")


@router.message(CampaignStates.waiting_for_price)
async def process_price(message: types.Message, state: FSMContext, session: AsyncSession):
    try:
        price = float(message.text.strip())
        if price < 0.1:
            raise ValueError()
        
        data = await state.get_data()
        budget = data.get("budget")
        await state.clear()

        user = await session.get(User, message.from_user.id)
        if float(user.balance) < budget:
            await message.answer("⚠️ Ошибка: на балансе недостаточно средств.", reply_markup=main_menu_kb())
            return

        user.balance -= Decimal(str(budget))
        new_order = Order(
            user_id=message.from_user.id,
            channel_id=-1001234567890,
            channel_title="Канал рекламодателя",
            channel_link="https://t.me/telegram",
            total_budget=Decimal(str(budget)),
            remaining_budget=Decimal(str(budget)),
            cpc_price=Decimal(str(price)),
            status="active"
        )
        session.add(new_order)
        await session.commit()

        await message.answer(
            f"✅ **Кампания успешно запущена!**\n\n"
            f"• Бюджет: {budget} RUB\n"
            f"• Ставка за подписку: {price} RUB",
            reply_markup=main_menu_kb()
        )
    except ValueError:
        await message.answer("⚠️ Введите корректную ставку (например, 1.20):")


# -------------------------------------------------------------
# Партнёрка
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:referrals")
async def nav_referrals(callback: types.CallbackQuery):
    await callback.answer()
    bot_me = await callback.bot.get_me()
    link = f"https://t.me/{bot_me.username}?start=ref_{callback.from_user.id}"
    text = (
        "🤝 **Партнёрская программа**\n\n"
        "• 5% от доходов рефералов 1-го уровня\n"
        "• 2% от рефералов 2-го уровня\n\n"
        f"🔗 Ссылка:\n`{link}`"
    )
    await callback.message.edit_text(text, reply_markup=back_kb(target="main_menu"), parse_mode="Markdown")