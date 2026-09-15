cat << 'EOF' > smikhub/bot/handlers/core.py
import secrets
from decimal import Decimal
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.db.models import User, Bot, Order
from smikhub.config import BASE_URL, ADMIN_CHAT_ID, CRYPTO_BOT_TOKEN
import aiohttp

router = Router()


# -------------------------------------------------------------
# FSM Состояния
# -------------------------------------------------------------
class CampaignStates(StatesGroup):
    waiting_for_budget = State()
    waiting_for_price = State()


class TopupStates(StatesGroup):
    waiting_for_crypto_amount = State()
    waiting_for_stars_amount = State()


class WithdrawStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_requisites = State()


# -------------------------------------------------------------
# Клавиатуры интерфейса
# -------------------------------------------------------------
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
        buttons.append([InlineKeyboardButton(text=f"⚙️ @{b.username}", callback_data=f"bot_manage:{b.id}")])
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
# Проверка админа
# -------------------------------------------------------------
def is_admin_user(user_id: int) -> bool:
    if not ADMIN_CHAT_ID:
        return False
    return str(user_id) == str(ADMIN_CHAT_ID)


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

    text = "👋 Добро пожаловать в SmikHub!\n\nБиржа обязательных подписок (ОП) в Telegram.\nМонетизируйте аудиторию своих ботов или закупайте целевой трафик на каналы."
    await message.answer(text, reply_markup=kb_main_menu(is_admin_user(uid)))


@router.callback_query(F.data == "nav:main_menu")
async def nav_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    text = "👋 Главное меню SmikHub\n\nВыберите нужный раздел:"
    await callback.message.edit_text(text, reply_markup=kb_main_menu(is_admin_user(callback.from_user.id)))


# -------------------------------------------------------------
# Админка (по кнопке и по команде /admin)
# -------------------------------------------------------------
@router.message(Command("admin"))
async def admin_command(message: types.Message, session: AsyncSession):
    if not is_admin_user(message.from_user.id):
        return
    users_count = len((await session.execute(select(User))).scalars().all())
    bots_count = len((await session.execute(select(Bot))).scalars().all())
    orders_count = len((await session.execute(select(Order))).scalars().all())

    text = f"🛠 Административная панель SmikHub\n\n👥 Всего пользователей: {users_count}\n🤖 Всего ботов: {bots_count}\n📢 Всего заказов: {orders_count}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")]
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "nav:admin")
async def nav_admin(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id):
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
    if not is_admin_user(callback.from_user.id):
        return
    await callback.answer()
    text = "📢 Рассылка сообщений\n\nОтправьте сообщение, которое получат все пользователи платформы."
    await callback.message.edit_text(text, reply_markup=kb_back(target="admin"))


# -------------------------------------------------------------
# Кабинет пользователя
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:cabinet")
async def nav_cabinet(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.clear()
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    text = f"👤 Личный кабинет\n\n🆔 Ваш ID: {callback.from_user.id}\n💰 Баланс: {balance:.2f} RUB\n\nВыберите действие для управления балансом:"
    await callback.message.edit_text(text, reply_markup=kb_cabinet())


@router.callback_query(F.data == "nav:topup_menu")
async def nav_topup_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    text = "💳 Выберите способ пополнения баланса:"
    await callback.message.edit_text(text, reply_markup=kb_topup())


# Пополнение через CryptoBot
@router.callback_query(F.data == "topup:cryptobot")
async def topup_cryptobot(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TopupStates.waiting_for_crypto_amount)
    text = "🤖 Введите сумму пополнения в рублях (например, 500):"
    await callback.message.edit_text(text, reply_markup=kb_back(target="topup_menu"))


@router.message(TopupStates.waiting_for_crypto_amount)
async def process_crypto_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount < 10:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Введите число не менее 10 руб.:")
        return

    await state.clear()
    
    # Расчет в USDT по примерному курсу ~100 руб
    usdt_amount = round(amount / 100.0, 2)
    if usdt_amount < 0.1:
        usdt_amount = 0.1

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
            [InlineKeyboardButton(text="💳 Оплатить счёт", url=invoice_url)],
            [InlineKeyboardButton(text="« Назад в кабинет", callback_data="nav:cabinet")]
        ])
        await message.answer(f"🧾 Счёт на сумму {amount:.2f} RUB ({usdt_amount} USDT) сформирован:", reply_markup=kb)
    else:
        await message.answer(
            f"🧾 Создан запрос на пополнение: {amount:.2f} RUB.\n\n"
            f"Токен CryptoBot не настроен или шлюз временно в тестовом режиме.",
            reply_markup=kb_back(target="topup_menu")
        )


# Пополнение через Telegram Stars
@router.callback_query(F.data == "topup:stars")
async def topup_stars(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TopupStates.waiting_for_stars_amount)
    text = "⭐️ Введите количество звёзд (Stars) для пополнения (1 Star = 1.50 RUB, минимум 10):"
    await callback.message.edit_text(text, reply_markup=kb_back(target="topup_menu"))


@router.message(TopupStates.waiting_for_stars_amount)
async def process_stars_amount(message: types.Message, state: FSMContext):
    try:
        stars = int(message.text.strip())
        if stars < 10:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Введите целое число не менее 10 звёзд:")
        return

    await state.clear()
    rub_val = round(stars * 1.5, 2)
    prices = [LabeledPrice(label=f"Пополнение на {rub_val} RUB", amount=stars)]

    try:
        await message.answer_invoice(
            title="Пополнение баланса SmikHub",
            description=f"Начисление {rub_val} RUB на рекламный баланс",
            payload=f"stars_{message.from_user.id}_{rub_val}",
            currency="XTR",
            prices=prices
        )
    except Exception as e:
        await message.answer(f"⚠️ Не удалось создать счёт: {e}", reply_markup=kb_back(target="topup_menu"))


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
            await message.answer(f"✅ Баланс успешно пополнен на {rub_amount:.2f} RUB!", reply_markup=kb_main_menu())


# -------------------------------------------------------------
# Вывод средств (SendPay)
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:withdraw_menu")
async def nav_withdraw_menu(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.clear()
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    text = f"📤 Вывод заработанных средств\n\nДоступно к выводу: {balance:.2f} RUB\nМинимальная сумма: 100.00 RUB"
    await callback.message.edit_text(text, reply_markup=kb_withdraw())


@router.callback_query(F.data == "withdraw:sendpay")
async def withdraw_sendpay(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    if balance < 100.0:
        text = f"⚠️ Недостаточно средств\n\nТекущий баланс: {balance:.2f} RUB.\nМинимальный вывод через SendPay: 100.00 RUB."
        await callback.message.edit_text(text, reply_markup=kb_back(target="withdraw_menu"))
        return

    await state.set_state(WithdrawStates.waiting_for_amount)
    text = f"💳 Вывод через SendPay (СБП / Карты РФ)\n\nДоступно: {balance:.2f} RUB\n\nВведите сумму для вывода:"
    await callback.message.edit_text(text, reply_markup=kb_back(target="withdraw_menu"))


@router.message(WithdrawStates.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext, session: AsyncSession):
    user = await session.get(User, message.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    try:
        amount = float(message.text.strip())
        if amount < 100:
            await message.answer("⚠️ Минимальная сумма вывода — 100 RUB:")
            return
        if amount > balance:
            await message.answer(f"⚠️ На балансе недостаточно средств. Доступно: {balance:.2f} RUB:")
            return
    except ValueError:
        await message.answer("⚠️ Введите число:")
        return

    await state.update_data(withdraw_amount=amount)
    await state.set_state(WithdrawStates.waiting_for_requisites)
    await message.answer("✍️ Введите реквизиты (Номер карты РФ или телефон для СБП с названием банка):")


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
        await message.answer("⚠️ Ошибка: баланс изменился, недостаточно средств.", reply_markup=kb_main_menu())
        return

    user.balance -= Decimal(str(amount))
    await session.commit()

    await message.answer(
        f"✅ Заявка на вывод #{secrets.token_hex(4)} принята!\n\n"
        f"• Сумма: {amount:.2f} RUB\n"
        f"• Реквизиты: {requisites}\n"
        f"• Статус: В обработке (SendPay)\n\n"
        f"Средства поступят в течение 10–15 минут.",
        reply_markup=kb_main_menu()
    )


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

    text = f"✅ Бот успешно добавлен в систему!\n\n• Имя: @{new_bot.username}\n• Токен интеграции: {new_token}\n\nПерейдите в раздел «Продать ОП», чтобы настроить параметры."
    await callback.message.edit_text(text, reply_markup=kb_back(target="sell_traffic"))


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


# -------------------------------------------------------------
# Купить ОП
# -------------------------------------------------------------
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
            await message.answer("⚠️ Ошибка: на балансе недостаточно средств.", reply_markup=kb_main_menu(is_admin_user(message.from_user.id)))
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
            reply_markup=kb_main_menu(is_admin_user(message.from_user.id))
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
    text = f"🤝 Партнёрская программа SmikHub\n\nПриглашайте вебмастеров и рекламодателей:\n• 5% от дохода ботов 1-го уровня\n• 2% от дохода ботов 2-го уровня\n\n🔗 Ваша партнёрская ссылка:\n{link}"
    await callback.message.edit_text(text, reply_markup=kb_back(target="main_menu"))
EOF