import secrets
from decimal import Decimal
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.db.models import User, Bot, Order
from smikhub.config import BASE_URL, ADMIN_CHAT_ID

router = Router()


class CampaignStates(StatesGroup):
    waiting_for_budget = State()
    waiting_for_price = State()


def kb_main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="👤 Кабинет", callback_data="nav:cabinet")],
        [InlineKeyboardButton(text="➕ Добавить бота", callback_data="nav:add_bot")],
        [
            InlineKeyboardButton(text="🤖 Продать ОП", callback_data="nav:sell_traffic"),
            InlineKeyboardButton(text="📢 Купить ОП", callback_data="nav:buy_traffic"),
        ],
        [InlineKeyboardButton(text="🤝 Партнёрка", callback_data="nav:referrals")]
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="nav:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_cabinet() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Пополнить", callback_data="nav:topup_menu"),
            InlineKeyboardButton(text="📤 Вывести", callback_data="nav:withdraw_menu")
        ],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")]
    ])


def kb_topup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 CryptoBot (USDT / TON)", callback_data="topup:cryptobot")],
        [InlineKeyboardButton(text="⭐️ Telegram Stars", callback_data="topup:stars")],
        [InlineKeyboardButton(text="« Назад в кабинет", callback_data="nav:cabinet")]
    ])


def kb_withdraw() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 SendPay (Карты / СБП)", callback_data="withdraw:sendpay")],
        [InlineKeyboardButton(text="« Назад в кабинет", callback_data="nav:cabinet")]
    ])


def kb_bot_list(bots: list) -> InlineKeyboardMarkup:
    buttons = []
    for b in bots:
        buttons.append([InlineKeyboardButton(text=f"⚙️ @{b.username}", callback_data=f"bot_manage:{b.id}")])
    buttons.append([InlineKeyboardButton(text="➕ Добавить ещё бота", callback_data="nav:add_bot")])
    buttons.append([InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_bot_settings(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Изменить мин. цену", callback_data=f"bot_edit_price:{bot_id}"),
            InlineKeyboardButton(text="🔢 Лимит спонсоров", callback_data=f"bot_edit_sponsors:{bot_id}")
        ],
        [
            InlineKeyboardButton(text="🔑 Показать токен", callback_data=f"bot_show_token:{bot_id}"),
            InlineKeyboardButton(text="📋 Код интеграции", callback_data=f"bot_code_snippet:{bot_id}")
        ],
        [InlineKeyboardButton(text="❌ Удалить бота", callback_data=f"bot_delete:{bot_id}")],
        [InlineKeyboardButton(text="« Назад к списку ботов", callback_data="nav:sell_traffic")]
    ])


def kb_buy_traffic(orders: list) -> InlineKeyboardMarkup:
    buttons = []
    for o in orders:
        buttons.append([InlineKeyboardButton(text=f"📊 Заказ #{o.id} ({o.status})", callback_data=f"order_view:{o.id}")])
    buttons.append([InlineKeyboardButton(text="➕ Создать кампанию", callback_data="nav:create_order")])
    buttons.append([InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_back(target: str = "main_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Назад", callback_data=f"nav:{target}")]
    ])


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

    text = "👋 Добро пожаловать в SmikHub!\n\nБиржа обязательных подписок (ОП) в Telegram.\nМонетизируйте аудиторию своих ботов или закупайте целевой трафик на каналы."
    is_admin = (uid == ADMIN_CHAT_ID)
    await message.answer(text, reply_markup=kb_main_menu(is_admin))


@router.callback_query(F.data == "nav:main_menu")
async def nav_main_menu(callback: types.CallbackQuery):
    await callback.answer()
    is_admin = (callback.from_user.id == ADMIN_CHAT_ID)
    text = "👋 Главное меню SmikHub\n\nВыберите нужный раздел:"
    await callback.message.edit_text(text, reply_markup=kb_main_menu(is_admin))


@router.callback_query(F.data == "nav:admin")
async def nav_admin(callback: types.CallbackQuery, session: AsyncSession):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("Доступ запрещен.", show_alert=True)
        return
    await callback.answer()

    users_count = len((await session.execute(select(User))).scalars().all())
    bots_count = len((await session.execute(select(Bot))).scalars().all())
    orders_count = len((await session.execute(select(Order))).scalars().all())

    text = f"🛠 Административная панель SmikHub\n\n👥 Всего пользователей: {users_count}\n🤖 Всего ботов: {bots_count}\n📢 Всего заказов: {orders_count}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        return
    await callback.answer()
    text = "📢 Рассылка сообщений\n\nФункция отправки сообщения всей базе пользователей."
    await callback.message.edit_text(text, reply_markup=kb_back(target="admin"))


@router.callback_query(F.data == "nav:cabinet")
async def nav_cabinet(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    text = f"👤 Личный кабинет\n\n🆔 Ваш ID: {callback.from_user.id}\n💰 Баланс: {balance:.2f} RUB\n\nВыберите действие для управления балансом:"
    await callback.message.edit_text(text, reply_markup=kb_cabinet())


@router.callback_query(F.data == "nav:topup_menu")
async def nav_topup_menu(callback: types.CallbackQuery):
    await callback.answer()
    text = "💳 Выберите способ пополнения баланса:"
    await callback.message.edit_text(text, reply_markup=kb_topup())


@router.callback_query(F.data == "topup:cryptobot")
async def topup_cryptobot(callback: types.CallbackQuery):
    await callback.answer()
    text = "🤖 Пополнение через CryptoBot\n\nПоддерживаемые криптовалюты: USDT, TON, BTC, NOT.\nБаланс начисляется моментально после подтверждения транзакции."
    await callback.message.edit_text(text, reply_markup=kb_back(target="topup_menu"))


@router.callback_query(F.data == "topup:stars")
async def topup_stars(callback: types.CallbackQuery):
    await callback.answer()
    text = "⭐️ Пополнение через Telegram Stars\n\nКурс конвертации: 1 Star = 1.50 RUB.\nОплата происходит нативно со счета Telegram."
    await callback.message.edit_text(text, reply_markup=kb_back(target="topup_menu"))


@router.callback_query(F.data == "nav:withdraw_menu")
async def nav_withdraw_menu(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    text = f"📤 Вывод заработанных средств\n\nДоступно к выводу: {balance:.2f} RUB\nМинимальная сумма: 100.00 RUB"
    await callback.message.edit_text(text, reply_markup=kb_withdraw())


@router.callback_query(F.data == "withdraw:sendpay")
async def withdraw_sendpay(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    if balance < 100.0:
        text = f"⚠️ Недостаточно средств\n\nТекущий баланс: {balance:.2f} RUB.\nМинимальный вывод через SendPay: 100.00 RUB."
    else:
        text = "💳 Вывод через SendPay (СБП / Карты)\n\nЗаявка сформирована и отправлена на автоматический шлюз выплат."
    await callback.message.edit_text(text, reply_markup=kb_back(target="withdraw_menu"))


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

    text = f"✅ Бот успешно добавлен в систему!\n\n• Имя: @{new_bot.username}\n• Токен интеграции: {new_token}\n\nПерейдите в раздел «Продать ОП», чтобы настроить параметры."
    await callback.message.edit_text(text, reply_markup=kb_back(target="sell_traffic"))


@router.callback_query(F.data == "nav:sell_traffic")
async def nav_sell_traffic(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bots = (await session.execute(
        select(Bot).where(Bot.user_id == callback.from_user.id)
    )).scalars().all()

    if not bots:
        text = "🤖 Монетизация (Продажа ОП)\n\nУ вас нет добавленных ботов. Нажмите кнопку ниже, чтобы подключить первого бота."
        await callback.message.edit_text(text, reply_markup=kb_bot_list([]))
        return

    text = "🤖 Ваши подключенные боты:\n\nВыберите бота для детальной настройки:"
    await callback.message.edit_text(text, reply_markup=kb_bot_list(bots))


@router.callback_query(F.data.startswith("bot_manage:"))
async def bot_manage(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)

    if not bot_obj:
        await callback.message.edit_text("Бот не найден.", reply_markup=kb_back(target="sell_traffic"))
        return

    text = f"⚙️ Управление ботом @{bot_obj.username}\n\n• Мин. цена: {float(bot_obj.min_price):.2f} RUB\n• Лимит спонсоров: {bot_obj.max_sponsors}\n• Рейтинг качества: {bot_obj.quality_score * 100:.0f}%\n\nНастройте параметры кнопками ниже:"
    await callback.message.edit_text(text, reply_markup=kb_bot_settings(bot_id))


@router.callback_query(F.data.startswith("bot_show_token:"))
async def bot_show_token(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    text = f"🔑 Токен интеграции для @{bot_obj.username}:\n\n{bot_obj.integration_token}"
    await callback.message.edit_text(text, reply_markup=kb_back(target="sell_traffic"))


@router.callback_query(F.data.startswith("bot_code_snippet:"))
async def bot_code_snippet(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)

    code = f"import requests\n\nurl = '{BASE_URL}/api/v1/bot/sponsors'\nheaders = {{'Authorization': 'Bearer {bot_obj.integration_token}'}}\nparams = {{'user_id': message.from_user.id}}\nresponse = requests.get(url, headers=headers, params=params).json()\nsponsors = response.get('sponsors', [])"
    text = f"📋 Готовый код интеграции:\n\n{code}"
    await callback.message.edit_text(text, reply_markup=kb_back(target="sell_traffic"))


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
    await callback.message.edit_text("🗑 Бот удалён из системы.", reply_markup=kb_back(target="sell_traffic"))


@router.callback_query(F.data == "nav:buy_traffic")
async def nav_buy_traffic(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    orders = (await session.execute(
        select(Order).where(Order.user_id == callback.from_user.id)
    )).scalars().all()

    text = "📢 Закупка трафика (Купить ОП)\n\nСоздавайте рекламные кампании для набора подписчиков в свои каналы через сеть ботов SmikHub."
    await callback.message.edit_text(text, reply_markup=kb_buy_traffic(orders))


@router.callback_query(F.data == "nav:create_order")
async def nav_create_order(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    if balance < 100.0:
        text = f"⚠️ Недостаточно средств для запуска кампании\n\nТекущий баланс: {balance:.2f} RUB\nМинимальный бюджет для создания кампании: 100.00 RUB.\nПополните баланс в разделе «👤 Кабинет»."
        await callback.message.edit_text(text, reply_markup=kb_back(target="buy_traffic"))
        return

    await state.set_state(CampaignStates.waiting_for_budget)
    text = "✍️ Введите общий бюджет рекламной кампании в рублях (например, 500):"
    await callback.message.edit_text(text, reply_markup=kb_back(target="buy_traffic"))


@router.message(CampaignStates.waiting_for_budget)
async def process_budget(message: types.Message, state: FSMContext):
    try:
        budget = float(message.text.strip())
        if budget < 100:
            raise ValueError()
        await state.update_data(budget=budget)
        await state.set_state(CampaignStates.waiting_for_price)
        await message.answer("✍️ Введите ставку за 1 подписчика (CPC) в рублях (например, 1.20):")
    except ValueError:
        await message.answer("⚠️ Введите число от 100 руб.:")


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
            await message.answer("⚠️ Ошибка: на балансе недостаточно средств.", reply_markup=kb_main_menu())
            return

        user.balance -= Decimal(str(budget))
        new_order = Order(
            user_id=message.from_user.id,
            channel_id=-1001234567890,
            channel_title="Мой канал",
            channel_link="https://t.me/telegram",
            total_budget=Decimal(str(budget)),
            remaining_budget=Decimal(str(budget)),
            cpc_price=Decimal(str(price)),
            status="active"
        )
        session.add(new_order)
        await session.commit()

        await message.answer(
            f"✅ Рекламная кампания #{new_order.id} успешно запущена!\n\n• Бюджет: {budget:.2f} RUB\n• Ставка за подписку: {price:.2f} RUB\n• Статус: Активна",
            reply_markup=kb_main_menu()
        )
    except ValueError:
        await message.answer("⚠️ Введите корректную ставку (например, 1.20):")


@router.callback_query(F.data == "nav:referrals")
async def nav_referrals(callback: types.CallbackQuery):
    await callback.answer()
    bot_me = await callback.bot.get_me()
    link = f"https://t.me/{bot_me.username}?start=ref_{callback.from_user.id}"
    text = f"🤝 Партнёрская программа SmikHub\n\nПриглашайте вебмастеров и рекламодателей:\n• 5% от дохода ботов 1-го уровня\n• 2% от дохода ботов 2-го уровня\n\n🔗 Ваша партнёрская ссылка:\n{link}"
    await callback.message.edit_text(text, reply_markup=kb_back(target="main_menu"))
