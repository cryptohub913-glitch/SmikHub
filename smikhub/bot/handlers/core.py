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


# -------------------------------------------------------------
# Клавиатуры интерфейса
# -------------------------------------------------------------
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


# -------------------------------------------------------------
# Главное меню
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
        "Монетизируйте аудиторию своих ботов или закупайте целевой трафик на каналы."
    )
    is_admin = (uid == ADMIN_CHAT_ID)
    await message.answer(text, reply_markup=kb_main_menu(is_admin), parse_mode="Markdown")


@router.callback_query(F.data == "nav:main_menu")
async def nav_main_menu(callback: types.CallbackQuery):
    await callback.answer()
    is_admin = (callback.from_user.id == ADMIN_CHAT_ID)
    text = "👋 **Главное меню SmikHub**\n\nВыберите нужный раздел:"
    await callback.message.edit_text(text, reply_markup=kb_main_menu(is_admin), parse_mode="Markdown")


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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        return
    await callback.answer()
    text = "📢 **Рассылка сообщений**\n\nФункция отправки сообщения всей базе пользователей."
    await callback.message.edit_text(text, reply_markup=kb_back(target="admin"), parse_mode="Markdown")


# -------------------------------------------------------------
# Кабинет
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
        f"Выберите действие для управления балансом:"
    )
    await callback.message.edit_text(text, reply_markup=kb_cabinet(), parse_mode="Markdown")


@router.callback_query(F.data == "nav:topup_menu")
async def nav_topup_menu(callback: types.CallbackQuery):
    await callback.answer()
    text = "💳 **Выберите способ пополнения баланса:**"
    await callback.message.edit_text(text, reply_markup=kb_topup(), parse_mode="Markdown")


@router.callback_query(F.data == "topup:cryptobot")
async def topup_cryptobot(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "🤖 **Пополнение через CryptoBot**\n\n"
        "Поддерживаемые криптовалюты: USDT, TON, BTC, NOT.\n"
        "Баланс начисляется моментально после подтверждения транзакции."
    )
    await callback.message.edit_text(text, reply_markup=kb_back(target="topup_menu"), parse_mode="Markdown")


@router.callback_query(F.data == "topup:stars")
async def topup_stars(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "⭐️ **Пополнение через Telegram Stars**\n\n"
        "Курс конвертации: 1 Star = 1.50 RUB.\n"
        "Оплата происходит нативно со счета Telegram."
    )
    await callback.message.edit_text(text, reply_markup=kb_back(target="topup_menu"), parse_mode="Markdown")


@router.callback_query(F.data == "nav:withdraw_menu")
async def nav_withdraw_menu(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    text = (
        f"📤 **Вывод заработанных средств**\n\n"
        f"Доступно к выводу: **{balance:.2f} RUB**\n"
        f"Минимальная сумма: **100.00 RUB**"
    )
    await callback.message.edit_text(text, reply_markup=kb_withdraw(), parse_mode="Markdown")


@router.callback_query(F.data == "withdraw:sendpay")
async def withdraw_sendpay(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    if balance < 100.0:
        text = (
            "⚠️ **Недостаточно средств**\n\n"
            f"Текущий баланс: **{balance:.2f} RUB**.\n"
            "Минимальный вывод через SendPay: **100.00 RUB**."
        )
    else:
        text = (
            "💳 **Вывод через SendPay (СБП / Карты)**\n\n"
            "Заявка сформирована и отправлена на автоматический шлюз выплат."
        )
    await callback.message.edit_text(text, reply_markup=kb_back(target="withdraw_menu"), parse_mode="Markdown")


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
        f"• Токен интеграции: `{new_token}`\n\n"
        "Перейдите в раздел «Продать ОП», чтобы настроить параметры."
    )
    await callback.message.edit_text(text, reply_markup=kb_back(target="sell_traffic"), parse_mode="Markdown")


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
            "🤖 **Монетизация (Продажа ОП)**\n\n"
            "У вас нет добавленных ботов. Нажмите кнопку ниже, чтобы подключить первого бота."
        )
        await callback.message.edit_text(text, reply_markup=kb_bot_list([]), parse_mode="Markdown")
        return

    text = "🤖 **Ваши подключенные боты:**\n\nВыберите бота для детальной настройки:"
    await callback.message.edit_text(text, reply_markup=kb_bot_list(bots), parse_mode="Markdown")


@router.callback_query(F.data.startswith("bot_manage:"))
async def bot_manage(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)

    if not bot_obj:
        await callback.message.edit_text("Бот не найден.", reply_markup=kb_back(target="sell_traffic"))
        return

    text = (
        f"⚙️ **Управление ботом @{bot_obj.username}**\n\n"
        f"• Мин. цена: **{float(bot_obj.min_price):.2f} RUB**\n"
        f"• Лимит спонсоров: **{bot_obj.max_sponsors}**\n"
        f"• Рейтинг качества: **{bot_obj.quality_score * 100:.0f}%**\n\n"
        "Настройте параметры кнопками ниже:"
    )
    await callback.message.edit_text(text, reply_markup=kb_bot_settings(bot_id), parse_mode="Markdown")


@router.callback_query(F.data.startswith("bot_show_token:"))
async def bot_show_token(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    text = f"🔑 **Токен интеграции для @{bot_obj.username}:**\n\n`{bot_obj.integration_token}`"
    await callback.message.edit_text(text, reply_markup=kb_back(target="sell_traffic"), parse_mode="Markdown")


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
        "sponsors = response.get('sponsors', [])\n"
        "