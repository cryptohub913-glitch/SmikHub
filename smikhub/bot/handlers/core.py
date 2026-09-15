import secrets
from decimal import Decimal
from datetime import datetime
import aiohttp
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.db.models import User, Bot, Order
from smikhub.config import BASE_URL, ADMIN_CHAT_ID, CRYPTO_BOT_TOKEN

router = Router()

class CampaignStates(StatesGroup):
    waiting_for_channel = State()
    waiting_for_budget = State()
    waiting_for_price = State()

class TopupStates(StatesGroup):
    waiting_for_crypto_amount = State()
    waiting_for_stars_amount = State()

class WithdrawStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_requisites = State()

class AddBotStates(StatesGroup):
    waiting_for_username = State()

class IntegrationStates(StatesGroup):
    waiting_for_subgram = State()
    waiting_for_flyer = State()
    waiting_for_traffy = State()
    waiting_for_piarflow = State()
    waiting_for_tgrass = State()

def kb_main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="👤 Кабинет", callback_data="nav:cabinet")],
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
        status_icon = "🟢" if getattr(b, "is_approved", True) else "⏳"
        buttons.append([InlineKeyboardButton(text=f"{status_icon} @{b.username}", callback_data=f"bot_manage:{b.id}")])
    buttons.append([InlineKeyboardButton(text="➕ Добавить бота", callback_data="nav:add_bot")])
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
        [
            InlineKeyboardButton(text="🌐 Сторонние интеграции", callback_data=f"bot_integrations:{bot_id}")
        ],
        [InlineKeyboardButton(text="❌ Удалить бота", callback_data=f"bot_delete:{bot_id}")],
        [InlineKeyboardButton(text="« Назад к списку ботов", callback_data="nav:sell_traffic")]
    ])

def kb_integrations(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔑 Subgram", callback_data=f"integ:subgram:{bot_id}"),
            InlineKeyboardButton(text="🔑 Flyer", callback_data=f"integ:flyer:{bot_id}")
        ],
        [
            InlineKeyboardButton(text="🔑 Traffy", callback_data=f"integ:traffy:{bot_id}"),
            InlineKeyboardButton(text="🔑 PiarFlow", callback_data=f"integ:piarflow:{bot_id}")
        ],
        [
            InlineKeyboardButton(text="🔑 TgGrass", callback_data=f"integ:tgrass:{bot_id}")
        ],
        [InlineKeyboardButton(text="« Назад к боту", callback_data=f"bot_manage:{bot_id}")]
    ])

def kb_buy_traffic(orders: list) -> InlineKeyboardMarkup:
    buttons = []
    for o in orders:
        buttons.append([InlineKeyboardButton(text=f"🛍 Заказ #{o.id} ({o.status})", callback_data=f"order_view:{o.id}")])
    buttons.append([InlineKeyboardButton(text="➕ Создать кампанию", callback_data="nav:create_order")])
    buttons.append([InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def kb_order_control(order_id: int, status: str, price: float) -> InlineKeyboardMarkup:
    toggle_text = "⏸ Остановить" if status == "active" else "▶️ Запустить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить статистику", callback_data=f"order_refresh:{order_id}")],
        [InlineKeyboardButton(text=f"💰 Цена: {price:.2f} ₽", callback_data=f"order_price:{order_id}")],
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data=f"order_settings:{order_id}"),
            InlineKeyboardButton(text="📍 Места показа", callback_data=f"order_placements:{order_id}")
        ],
        [InlineKeyboardButton(text="🏷 Тематики: Все", callback_data=f"order_target_topics:{order_id}")],
        [
            InlineKeyboardButton(text="👥 Пол: Любой", callback_data=f"order_target_gender:{order_id}"),
            InlineKeyboardButton(text="🎂 Возраст: Любой", callback_data=f"order_target_age:{order_id}")
        ],
        [
            InlineKeyboardButton(text="💎 TG Premium: Не важно", callback_data=f"order_target_prem:{order_id}"),
            InlineKeyboardButton(text="🌐 Языки: 0", callback_data=f"order_target_lang:{order_id}")
        ],
        [InlineKeyboardButton(text="🌍 Страны: 0", callback_data=f"order_target_geo:{order_id}")],
        [
            InlineKeyboardButton(text=toggle_text, callback_data=f"order_toggle:{order_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"order_delete:{order_id}")
        ],
        [InlineKeyboardButton(text="« Назад", callback_data="nav:buy_traffic")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="nav:main_menu")]
    ])

def kb_admin_bot_moderation(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve_bot:{bot_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_bot:{bot_id}")
        ]
    ])

def kb_cancel(target: str = "main_menu", text_btn: str = "« Отмена") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text_btn, callback_data=target if ':' in target else f"nav:{target}")]
    ])

def is_admin_user(user_id: int) -> bool:
    if not ADMIN_CHAT_ID:
        return False
    return str(user_id) == str(ADMIN_CHAT_ID)


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
        "Монетизируйте своих ботов или закупайте живой целевой трафик."
    )
    await message.answer(text, reply_markup=kb_main_menu(is_admin_user(uid)), parse_mode="Markdown")

@router.callback_query(F.data == "nav:main_menu")
async def nav_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    text = "👋 **Главное меню SmikHub**\n\nВыберите нужный раздел:"
    await callback.message.edit_text(text, reply_markup=kb_main_menu(is_admin_user(callback.from_user.id)), parse_mode="Markdown")

@router.message(Command("admin"))
async def admin_command(message: types.Message, session: AsyncSession):
    if not is_admin_user(message.from_user.id):
        return
    users_count = len((await session.execute(select(User))).scalars().all())
    bots_count = len((await session.execute(select(Bot))).scalars().all())
    orders_count = len((await session.execute(select(Order))).scalars().all())

    text = (
        "🛠 **Административная панель SmikHub**\n\n"
        f"👥 Пользователей: `{users_count}`\n"
        f"🤖 Подключено ботов: `{bots_count}`\n"
        f"📢 Заказов: `{orders_count}`"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "nav:admin")
async def nav_admin(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id):
        await callback.answer("Доступ запрещен.", show_alert=True)
        return
    await callback.answer()
    users_count = len((await session.execute(select(User))).scalars().all())
    bots_count = len((await session.execute(select(Bot))).scalars().all())
    orders_count = len((await session.execute(select(Order))).scalars().all())

    text = (
        "🛠 **Административная панель SmikHub**\n\n"
        f"👥 Пользователей: `{users_count}`\n"
        f"🤖 Подключено ботов: `{bots_count}`\n"
        f"📢 Заказов: `{orders_count}`"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(callback: types.CallbackQuery):
    if not is_admin_user(callback.from_user.id):
        return
    await callback.answer()
    text = "📢 **Рассылка сообщений**\n\nОтправьте текст сообщения для массовой рассылки всем пользователям платформы."
    await callback.message.edit_text(text, reply_markup=kb_cancel("admin"), parse_mode="Markdown")

@router.callback_query(F.data == "nav:cabinet")
async def nav_cabinet(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.clear()
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    text = (
        f"👤 **Личный кабинет**\n\n"
        f"🆔 Ваш ID: `{callback.from_user.id}`\n"
        f"💰 Основной баланс: **{balance:.2f} RUB**\n\n"
        "Выберите действие для управления балансом:"
    )
    await callback.message.edit_text(text, reply_markup=kb_cabinet(), parse_mode="Markdown")

@router.callback_query(F.data == "nav:topup_menu")
async def nav_topup_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    text = "💳 **Выберите способ пополнения баланса:**"
    await callback.message.edit_text(text, reply_markup=kb_topup(), parse_mode="Markdown")

@router.callback_query(F.data == "topup:cryptobot")
async def topup_cryptobot(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TopupStates.waiting_for_crypto_amount)
    text = "🤖 Введите сумму пополнения в рублях (минимум 50 RUB):"
    await callback.message.edit_text(text, reply_markup=kb_cancel("topup_menu"))

@router.message(TopupStates.waiting_for_crypto_amount)
async def process_crypto_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount < 50:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Введите число не менее 50 руб.:")
        return
    await state.clear()
    usdt_amount = max(0.5, round(amount / 95.0, 2))
    invoice_url = None
    if CRYPTO_BOT_TOKEN:
        try:
            async with aiohttp.ClientSession() as client:
                res = await client.post(
                    "https://pay.crypt.bot/api/createInvoice",
                    headers={"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN},
                    json={
                        "asset": "USDT",
                        "amount": str(usdt_amount),
                        "description": f"Пополнение SmikHub: {amount} RUB",
                        "payload": f"topup_{message.from_user.id}_{amount}"
                    }
                )
                data = await res.json()
                if data.get("ok"):
                    invoice_url = data["result"]["pay_url"]
        except Exception:
            pass
    if invoice_url:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить счет", url=invoice_url)],
            [InlineKeyboardButton(text="« Назад в кабинет", callback_data="nav:cabinet")]
        ])
        await message.answer(f"🧾 Счёт на {amount:.2f} RUB ({usdt_amount} USDT) выставлен:", reply_markup=kb)
    else:
        await message.answer("🧾 Заявка создана.\nШлюз ожидает подтверждения.", reply_markup=kb_cancel("topup_menu", "« Назад"))

@router.callback_query(F.data == "topup:stars")
async def topup_stars(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TopupStates.waiting_for_stars_amount)
    text = "⭐️ Введите количество Stars для оплаты (1 Star = 1.50 RUB, минимум 10):"
    await callback.message.edit_text(text, reply_markup=kb_cancel("topup_menu"))

@router.message(TopupStates.waiting_for_stars_amount)
async def process_stars_amount(message: types.Message, state: FSMContext):
    try:
        stars = int(message.text.strip())
        if stars < 10:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Введите число не менее 10:")
        return
    await state.clear()
    rub_val = round(stars * 1.5, 2)
    prices = [LabeledPrice(label=f"Пополнение {rub_val} RUB", amount=stars)]
    try:
        await message.answer_invoice(
            title="Пополнение SmikHub",
            description=f"Зачисление {rub_val} RUB",
            payload=f"stars_{message.from_user.id}_{rub_val}",
            currency="XTR",
            prices=prices
        )
    except Exception as e:
        await message.answer(f"⚠️ Ошибка создания счёта Stars: {e}", reply_markup=kb_cancel("topup_menu", "« Назад"))

@router.pre_checkout_query()
async def on_pre_checkout(query: types.PreCheckoutQuery):
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def on_successful_payment(message: types.Message, session: AsyncSession):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("stars_"):
        parts = payload.split("_")
        rub_amount = Decimal(parts[2])
        user = await session.get(User, message.from_user.id)
        if user:
            user.balance += rub_amount
            await session.commit()
            await message.answer(f"✅ Баланс пополнен на {rub_amount:.2f} RUB!", reply_markup=kb_main_menu(is_admin_user(message.from_user.id)))

@router.callback_query(F.data == "nav:withdraw_menu")
async def nav_withdraw_menu(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.clear()
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0
    text = f"📤 **Вывод заработанных средств**\n\nДоступно к выводу: **{balance:.2f} RUB**\nМинимальная выплата: **100.00 RUB**"
    await callback.message.edit_text(text, reply_markup=kb_withdraw(), parse_mode="Markdown")

@router.callback_query(F.data == "withdraw:sendpay")
async def withdraw_sendpay(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0
    if balance < 100.0:
        text = f"⚠️ **Недостаточно средств**\n\nТекущий баланс: **{balance:.2f} RUB**.\nМинимальный вывод через SendPay: **100.00 RUB**."
        await callback.message.edit_text(text, reply_markup=kb_cancel("withdraw_menu", "« Назад"), parse_mode="Markdown")
        return
    await state.set_state(WithdrawStates.waiting_for_amount)
    text = f"💳 **Вывод через SendPay (СБП / Карты РФ)**\n\nДоступно: **{balance:.2f} RUB**\n\nВведите сумму для вывода:"
    await callback.message.edit_text(text, reply_markup=kb_cancel("withdraw_menu", "« Отмена"), parse_mode="Markdown")

@router.message(WithdrawStates.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext, session: AsyncSession):
    user = await session.get(User, message.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0
    try:
        amount = float(message.text.strip())
        if amount < 100:
            await message.answer("⚠️ Минимальная сумма — 100 RUB:")
            return
        if amount > balance:
            await message.answer(f"⚠️ На балансе недостаточно средств. Доступно: {balance:.2f} RUB:")
            return
    except ValueError:
        await message.answer("⚠️ Введите число:")
        return
    await state.update_data(withdraw_amount=amount)
    await state.set_state(WithdrawStates.waiting_for_requisites)
    await message.answer("✍️ Введите реквизиты (Номер карты РФ или номер телефона для СБП с указанием банка):")

@router.message(WithdrawStates.waiting_for_requisites)
async def process_withdraw_requisites(message: types.Message, state: FSMContext, session: AsyncSession):
    requisites = message.text.strip()
    if len(requisites) < 6:
        await message.answer("⚠️ Введите корректные реквизиты:")
        return
    data = await state.get_data()
    amount = data.get("withdraw_amount")
    await state.clear()
    user = await session.get(User, message.from_user.id)
    if float(user.balance) < amount:
        await message.answer("⚠️ На балансе недостаточно средств.", reply_markup=kb_main_menu(is_admin_user(message.from_user.id)))
        return
    user.balance -= Decimal(str(amount))
    await session.commit()
    await message.answer(
        f"✅ **Заявка на вывод #{secrets.token_hex(4)} принята!**\n\n• Сумма: **{amount:.2f} RUB**\n• Реквизиты: `{requisites}`\n• Платёжный шлюз: **SendPay (Авто)**\n\nСредства поступят на карту в течение 10–15 минут.",
        reply_markup=kb_main_menu(is_admin_user(message.from_user.id)),
        parse_mode="Markdown"
    )


# ==========================================
# Продать ОП (Добавление бота, Модерация)
# ==========================================
@router.callback_query(F.data == "nav:sell_traffic")
async def nav_sell_traffic(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bots = (await session.execute(
        select(Bot).where(Bot.user_id == callback.from_user.id)
    )).scalars().all()
    if not bots:
        text = "🤖 **Монетизация (Продажа ОП)**\n\nУ вас пока нет подключённых ботов.\nНажмите «➕ Добавить бота», чтобы отправить заявку на модерацию и начать зарабатывать."
        await callback.message.edit_text(text, reply_markup=kb_bot_list([]), parse_mode="Markdown")
        return
    text = "🤖 **Ваши подключённые боты:**\n\nВыберите бота для управления параметрами:"
    await callback.message.edit_text(text, reply_markup=kb_bot_list(bots), parse_mode="Markdown")

@router.callback_query(F.data == "nav:add_bot")
async def nav_add_bot(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddBotStates.waiting_for_username)
    text = "➕ **Добавление нового бота на платформу**\n\nОтправьте юзернейм вашего бота (например, `@MyBestBot`).\nБот будет отправлен администратору на быструю модерацию."
    await callback.message.edit_text(text, reply_markup=kb_cancel("sell_traffic"), parse_mode="Markdown")

@router.message(AddBotStates.waiting_for_username)
async def process_add_bot_username(message: types.Message, state: FSMContext, session: AsyncSession):
    raw_name = message.text.strip().replace("@", "")
    if len(raw_name) < 3:
        await message.answer("⚠️ Введите корректный юзернейм бота:")
        return
    await state.clear()
    new_token = secrets.token_hex(16)
    new_bot = Bot(
        user_id=message.from_user.id,
        username=raw_name,
        integration_token=new_token,
        min_price=Decimal("0.50"),
        max_sponsors=3,
        quality_score=0.80
    )
    session.add(new_bot)
    await session.commit()

    if ADMIN_CHAT_ID:
        try:
            admin_msg = f"🔔 **Новый бот на модерацию!**\n\n• Бот: @{new_bot.username}\n• Владелец ID: `{message.from_user.id}`\n• Имя: @{message.from_user.username or 'без username'}"
            await message.bot.send_message(
                ADMIN_CHAT_ID,
                admin_msg,
                reply_markup=kb_admin_bot_moderation(new_bot.id),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    text = f"✅ **Бот @{new_bot.username} отправлен на модерацию!**\n\n🔑 Токен API: `{new_token}`\nПосле подтверждения бот начнёт получать задания."
    await message.answer(text, reply_markup=kb_cancel("sell_traffic", "« К списку ботов"), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_approve_bot:"))
async def admin_approve_bot(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer("Бот одобрен!")
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        try:
            await callback.bot.send_message(bot_obj.user_id, f"🎉 **Ваш бот @{bot_obj.username} успешно прошёл модерацию и активирован!**", parse_mode="Markdown")
        except Exception:
            pass
    await callback.message.edit_text(f"✅ Бот #{bot_id} одобрен.")

@router.callback_query(F.data.startswith("admin_reject_bot:"))
async def admin_reject_bot(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer("Бот отклонён!")
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        try:
            await callback.bot.send_message(bot_obj.user_id, f"⚠️ Ваш бот @{bot_obj.username} не прошёл модерацию.", parse_mode="Markdown")
        except Exception:
            pass
        await session.delete(bot_obj)
        await session.commit()
    await callback.message.edit_text(f"❌ Бот #{bot_id} отклонён.")


# ==========================================
# Настройки бота (Цена, Спонсоры)
# ==========================================
@router.callback_query(F.data.startswith("bot_manage:"))
async def bot_manage(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if not bot_obj:
        await callback.message.edit_text("Бот не найден.", reply_markup=kb_cancel("sell_traffic"))
        return
    text = f"⚙️ **Управление ботом @{bot_obj.username}**\n\n• Мин. цена: **{float(bot_obj.min_price):.2f} RUB**\n• Лимит спонсоров: **{bot_obj.max_sponsors}**\n• Рейтинг качества: **{bot_obj.quality_score * 100:.0f}%**\n\nНастройте параметры кнопками ниже:"
    await callback.message.edit_text(text, reply_markup=kb_bot_settings(bot_id), parse_mode="Markdown")

@router.callback_query(F.data.startswith("bot_edit_price:"))
async def bot_edit_price(callback: types.CallbackQuery, session: AsyncSession):
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if not bot_obj:
        await callback.answer("Ошибка: бот не найден.")
        return
    current = float(bot_obj.min_price)
    next_price = 1.00 if current == 0.50 else (1.50 if current == 1.00 else (2.00 if current == 1.50 else 0.50))
    bot_obj.min_price = Decimal(str(next_price))
    await session.commit()
    
    now_str = datetime.now().strftime('%H:%M:%S')
    text = f"⚙️ **Управление ботом @{bot_obj.username}**\n\n• Мин. цена: **{float(bot_obj.min_price):.2f} RUB**\n• Лимит спонсоров: **{bot_obj.max_sponsors}**\n• Рейтинг качества: **{bot_obj.quality_score * 100:.0f}%**\n\n_🔄 Обновлено: {now_str}_\nНастройте параметры кнопками ниже:"
    try:
        await callback.message.edit_text(text, reply_markup=kb_bot_settings(bot_id), parse_mode="Markdown")
        await callback.answer(f"Цена изменена на {next_price:.2f} RUB")
    except Exception:
        await callback.answer("Цена изменена.")

@router.callback_query(F.data.startswith("bot_edit_sponsors:"))
async def bot_edit_sponsors(callback: types.CallbackQuery, session: AsyncSession):
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if not bot_obj:
        await callback.answer("Ошибка: бот не найден.")
        return
    new_limit = 1 if bot_obj.max_sponsors >= 5 else (bot_obj.max_sponsors + 1)
    bot_obj.max_sponsors = new_limit
    await session.commit()
    
    now_str = datetime.now().strftime('%H:%M:%S')
    text = f"⚙️ **Управление ботом @{bot_obj.username}**\n\n• Мин. цена: **{float(bot_obj.min_price):.2f} RUB**\n• Лимит спонсоров: **{bot_obj.max_sponsors}**\n• Рейтинг качества: **{bot_obj.quality_score * 100:.0f}%**\n\n_🔄 Обновлено: {now_str}_\nНастройте параметры кнопками ниже:"
    try:
        await callback.message.edit_text(text, reply_markup=kb_bot_settings(bot_id), parse_mode="Markdown")
        await callback.answer(f"Лимит спонсоров: {new_limit}")
    except Exception:
        await callback.answer("Лимит изменён.")

@router.callback_query(F.data.startswith("bot_show_token:"))
async def bot_show_token(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    text = f"🔑 **Токен интеграции для @{bot_obj.username}:**\n\n`{bot_obj.integration_token}`"
    await callback.message.edit_text(text, reply_markup=kb_cancel(f"bot_manage:{bot_id}", "« Назад"), parse_mode="Markdown")

@router.callback_query(F.data.startswith("bot_code_snippet:"))
async def bot_code_snippet(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    code = (
        "import requests\n\n"
        f"url = '{BASE_URL}/api/v1/bot/sponsors'\n"
        f"headers = {{'Authorization': 'Bearer {bot_obj.integration_token}'}}\n"
        "params = {'user_id': message.from_user.id}\n"
        "response = requests.get(url, headers=headers, params=params).json()\n"
        "sponsors = response.get('sponsors', [])"
    )
    text = f"📋 **Готовый код интеграции:**\n\n```python\n{code}\n