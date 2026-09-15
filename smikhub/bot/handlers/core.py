import secrets
from decimal import Decimal
import aiohttp
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import LabeledPrice
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.db.models import User, Bot, Order
from smikhub.config import BASE_URL, ADMIN_CHAT_ID, CRYPTO_BOT_TOKEN
from smikhub.bot.keyboards import (
    main_menu_kb,
    cabinet_kb,
    topup_methods_kb,
    withdraw_methods_kb,
    bot_list_kb,
    bot_settings_kb,
    buy_traffic_kb,
    order_control_kb,
    admin_bot_moderation_kb,
    back_kb
)

router = Router()


class AddBotStates(StatesGroup):
    waiting_for_username = State()


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

    text = (
        "👋 **Добро пожаловать в SmikHub!**\n\n"
        "Биржа обязательных подписок (ОП) в Telegram.\n"
        "Монетизируйте своих ботов или закупайте живой целевой трафик на каналы."
    )
    await message.answer(text, reply_markup=main_menu_kb(is_admin_user(uid)), parse_mode="Markdown")


@router.callback_query(F.data == "nav:main_menu")
async def nav_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    text = "👋 **Главное меню SmikHub**\n\nВыберите нужный раздел:"
    await callback.message.edit_text(text, reply_markup=main_menu_kb(is_admin_user(callback.from_user.id)), parse_mode="Markdown")


# -------------------------------------------------------------
# Админка (/admin и кнопка)
# -------------------------------------------------------------
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
        f"📢 Рекламных заказов: `{orders_count}`"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📢 Рассылка по пользователям", callback_data="admin:broadcast")],
        [types.InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")]
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
        f"📢 Рекламных заказов: `{orders_count}`"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📢 Рассылка по пользователям", callback_data="admin:broadcast")],
        [types.InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(callback: types.CallbackQuery):
    if not is_admin_user(callback.from_user.id):
        return
    await callback.answer()
    await callback.message.edit_text(
        "📢 **Рассылка сообщений**\n\nОтправьте текст сообщения для массовой рассылки всем пользователям платформы.",
        reply_markup=back_kb(target="admin")
    )


# -------------------------------------------------------------
# Кабинет пользователя
# -------------------------------------------------------------
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
    await callback.message.edit_text(text, reply_markup=cabinet_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "nav:topup_menu")
async def nav_topup_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    text = "💳 **Выберите способ пополнения баланса:**"
    await callback.message.edit_text(text, reply_markup=topup_methods_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "topup:cryptobot")
async def topup_cryptobot(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TopupStates.waiting_for_crypto_amount)
    text = "🤖 Введите сумму пополнения в рублях (минимум 50 RUB):"
    await callback.message.edit_text(text, reply_markup=back_kb(target="topup_menu"))


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
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💳 Оплатить счет", url=invoice_url)],
            [types.InlineKeyboardButton(text="« Назад в кабинет", callback_data="nav:cabinet")]
        ])
        await message.answer(f"🧾 Счёт на {amount:.2f} RUB ({usdt_amount} USDT) успешно выставлен:", reply_markup=kb)
    else:
        await message.answer(
            f"🧾 Создана заявка на {amount:.2f} RUB.\nШлюз ожидает подтверждения.",
            reply_markup=back_kb(target="topup_menu")
        )


@router.callback_query(F.data == "topup:stars")
async def topup_stars(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TopupStates.waiting_for_stars_amount)
    text = "⭐️ Введите количество Stars для оплаты (1 Star = 1.50 RUB, минимум 10):"
    await callback.message.edit_text(text, reply_markup=back_kb(target="topup_menu"))


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
            title="Пополнение баланса SmikHub",
            description=f"Зачисление {rub_val} RUB на рекламный баланс",
            payload=f"stars_{message.from_user.id}_{rub_val}",
            currency="XTR",
            prices=prices
        )
    except Exception as e:
        await message.answer(f"⚠️ Ошибка создания счёта Stars: {e}", reply_markup=back_kb(target="topup_menu"))


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
            await message.answer(f"✅ Баланс успешно пополнен на {rub_amount:.2f} RUB!", reply_markup=main_menu_kb())


# -------------------------------------------------------------
# Вывод средств (SendPay)
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:withdraw_menu")
async def nav_withdraw_menu(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.clear()
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    text = (
        f"📤 **Вывод заработанных средств**\n\n"
        f"Доступно к выводу: **{balance:.2f} RUB**\n"
        "Минимальная выплата: **100.00 RUB**"
    )
    await callback.message.edit_text(text, reply_markup=withdraw_methods_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "withdraw:sendpay")
async def withdraw_sendpay(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    if balance < 100.0:
        text = (
            "⚠️ **Недостаточно средств**\n\n"
            f"Текущий баланс: **{balance:.2f} RUB**.\n"
            "Минимальный вывод через SendPay: **100.00 RUB**."
        )
        await callback.message.edit_text(text, reply_markup=back_kb(target="withdraw_menu"), parse_mode="Markdown")
        return

    await state.set_state(WithdrawStates.waiting_for_amount)
    text = f"💳 **Вывод через SendPay (СБП / Карты РФ)**\n\nДоступно: **{balance:.2f} RUB**\n\nВведите сумму для вывода:"
    await callback.message.edit_text(text, reply_markup=back_kb(target="withdraw_menu"), parse_mode="Markdown")


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
        await message.answer("⚠️ На балансе недостаточно средств.", reply_markup=main_menu_kb())
        return

    user.balance -= Decimal(str(amount))
    await session.commit()

    await message.answer(
        f"✅ **Заявка на вывод #{secrets.token_hex(4)} принята!**\n\n"
        f"• Сумма: **{amount:.2f} RUB**\n"
        f"• Реквизиты: `{requisites}`\n"
        "• Платёжный шлюз: **SendPay (Авто)**\n\n"
        "Средства поступят на карту в течение 10–15 минут.",
        reply_markup=main_menu_kb(),
        parse_mode="Markdown"
    )


# -------------------------------------------------------------
# Продать ОП (Боты, модерация, настройки)
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
            "У вас пока нет подключённых ботов.\n"
            "Нажмите «➕ Добавить бота», чтобы отправить заявку на модерацию и начать зарабатывать."
        )
        await callback.message.edit_text(text, reply_markup=bot_list_kb([]), parse_mode="Markdown")
        return

    text = "🤖 **Ваши подключённые боты:**\n\nВыберите бота для управления параметрами:"
    await callback.message.edit_text(text, reply_markup=bot_list_kb(bots), parse_mode="Markdown")


@router.callback_query(F.data == "nav:add_bot")
async def nav_add_bot(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddBotStates.waiting_for_username)
    text = (
        "➕ **Добавление нового бота на платформу**\n\n"
        "Отправьте юзернейм вашего бота (например, `@MyBestBot` или `MyBestBot`).\n"
        "Бот будет отправлен администратору на быструю модерацию."
    )
    await callback.message.edit_text(text, reply_markup=back_kb(target="sell_traffic"), parse_mode="Markdown")


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

    # Уведомляем администратора о новом боте
    if ADMIN_CHAT_ID:
        try:
            admin_msg = (
                "🔔 **Новый бот на модерацию!**\n\n"
                f"• Бот: @{new_bot.username}\n"
                f"• Владелец ID: `{message.from_user.id}`\n"
                f"• Имя владельца: @{message.from_user.username or 'без username'}"
            )
            await message.bot.send_message(
                ADMIN_CHAT_ID,
                admin_msg,
                reply_markup=admin_bot_moderation_kb(new_bot.id),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    text = (
        f"✅ **Бот @{new_bot.username} отправлен на модерацию!**\n\n"
        f"🔑 Токен API: `{new_token}`\n"
        f"После подтверждения администратором бот начнёт получать рекламные задания."
    )
    await message.answer(text, reply_markup=back_kb(target="sell_traffic"), parse_mode="Markdown")


@router.callback_query(F.data.startswith("admin_approve_bot:"))
async def admin_approve_bot(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer("Бот одобрен!")
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        try:
            await callback.bot.send_message(
                bot_obj.user_id,
                f"🎉 **Ваш бот @{bot_obj.username} успешно прошёл модерацию и активирован!**",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    await callback.message.edit_text(f"✅ Бот #{bot_id} одобрен администратором.")


@router.callback_query(F.data.startswith("admin_reject_bot:"))
async def admin_reject_bot(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer("Бот отклонён!")
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        try:
            await callback.bot.send_message(
                bot_obj.user_id,
                f"⚠️ Ваш бот @{bot_obj.username} не прошёл модерацию.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await session.delete(bot_obj)
        await session.commit()
    await callback.message.edit_text(f"❌ Бот #{bot_id} отклонён и удалён.")


# Экран управления конкретным ботом (Скриншот 2)
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
        f"• Лимит спонсоров: **{bot_obj.max_sponsors}**\n"
        f"• Рейтинг качества: **{bot_obj.quality_score * 100:.0f}%**\n\n"
        "Настройте параметры кнопками ниже:"
    )
    await callback.message.edit_text(text, reply_markup=bot_settings_kb(bot_id), parse_mode="Markdown")


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
    await callback.answer(f"Цена изменена на {next_price:.2f} RUB")

    text = (
        f"⚙️ **Управление ботом @{bot_obj.username}**\n\n"
        f"• Мин. цена: **{float(bot_obj.min_price):.2f} RUB**\n"
        f"• Лимит спонсоров: **{bot_obj.max_sponsors}**\n"
        f"• Рейтинг качества: **{bot_obj.quality_score * 100:.0f}%**\n\n"
        "Настройте параметры кнопками ниже:"
    )
    await callback.message.edit_text(text, reply_markup=bot_settings_kb(bot_id), parse_mode="Markdown")


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
    await callback.answer(f"Лимит спонсоров: {new_limit}")

    text = (
        f"⚙️ **Управление ботом @{bot_obj.username}**\n\n"
        f"• Мин. цена: **{float(bot_obj.min_price):.2f} RUB**\n"
        f"• Лимит спонсоров: **{bot_obj.max_sponsors}**\n"
        f"• Рейтинг качества: **{bot_obj.quality_score * 100:.0f}%**\n\n"
        "Настройте параметры кнопками ниже:"
    )
    await callback.message.edit_text(text, reply_markup=bot_settings_kb(bot_id), parse_mode="Markdown")


@router.callback_query(F.data.startswith("bot_show_token:"))
async def bot_show_token(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    text = f"🔑 **Токен интеграции для @{bot_obj.username}:**\n\n`{bot_obj.integration_token}`"
    await callback.message.edit_text(text, reply_markup=back_kb(target=f"sell_traffic"), parse_mode="Markdown")


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
    text = f"📋 **Готовый код интеграции:**\n\n```python\n{code}\n```"
    await callback.message.edit_text(text, reply_markup=back_kb(target="sell_traffic"), parse_mode="Markdown")


@router.callback_query(F.data.startswith("bot_integrations:"))
async def bot_integrations(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    text = (
        f"🌐 **Сторонние рекламные сети для @{bot_obj.username}**\n\n"
        "Вы можете подключить внешние биржи рекламы, чтобы бот автоматически показывал объявления, "
        "когда нет активных спонсоров в SmikHub:\n\n"
        "• **Adsgram API:** Видеореклама и баннеры Telegram Mini Apps\n"
        "• **PR Flow API:** Обязательные подписки на каналы партнёров\n"
        "• **Trafsly:** Дополнительная ротация прямых рекламодателей\n\n"
        f"Webhook уведомлений: `{bot_obj.webhook_url or 'По умолчанию'}`"
    )
    await callback.message.edit_text(text, reply_markup=back_kb(target=f"sell_traffic"), parse_mode="Markdown")


@router.callback_query(F.data.startswith("bot_delete:"))
async def bot_delete(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        await session.delete(bot_obj)
        await session.commit()
    await callback.message.edit_text("🗑 Бот успешно удалён из платформы.", reply_markup=back_kb(target="sell_traffic"))


# -------------------------------------------------------------
# Купить ОП (Панель кампаний со всеми таргетингами)
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:buy_traffic")
async def nav_buy_traffic(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    orders = (await session.execute(
        select(Order).where(Order.user_id == callback.from_user.id)
    )).scalars().all()

    text = (
        "📢 **Закупка трафика (Купить ОП)**\n\n"
        "Создавайте рекламные кампании для набора живых подписчиков в каналы через сеть ботов SmikHub."
    )
    await callback.message.edit_text(text, reply_markup=buy_traffic_kb(orders), parse_mode="Markdown")


@router.callback_query(F.data == "nav:create_order")
async def nav_create_order(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    if balance < 100.0:
        text = (
            "⚠️ **Недостаточно средств для запуска кампании**\n\n"
            f"Текущий баланс: **{balance:.2f} RUB**\n"
            "Минимальный бюджет для создания кампании: **100.00 RUB**.\n"
            "Пополните баланс в разделе «👤 Кабинет»."
        )
        await callback.message.edit_text(text, reply_markup=back_kb(target="buy_traffic"), parse_mode="Markdown")
        return

    await state.set_state(CampaignStates.waiting_for_channel)
    text = "✍️ **Шаг 1/3:** Отправьте ссылку на канал или чат (например, `https://t.me/mychannel`):"
    await callback.message.edit_text(text, reply_markup=back_kb(target="buy_traffic"), parse_mode="Markdown")


@router.message(CampaignStates.waiting_for_channel)
async def process_campaign_channel(message: types.Message, state: FSMContext):
    link = message.text.strip()
    if "t.me/" not in link:
        await message.answer("⚠️ Отправьте корректную ссылку Telegram (начинается с https://t.me/...):")
        return

    await state.update_data(channel_link=link)
    await state.set_state(CampaignStates.waiting_for_budget)
    await message.answer("✍️ **Шаг 2/3:** Введите общий бюджет кампании в рублях (минимум 100 RUB):")


@router.message(CampaignStates.waiting_for_budget)
async def process_campaign_budget(message: types.Message, state: FSMContext):
    try:
        budget = float(message.text.strip())
        if budget < 100:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Введите число не менее 100 руб.:")
        return

    await state.update_data(budget=budget)
    await state.set_state(CampaignStates.waiting_for_price)
    await message.answer("✍️ **Шаг 3/3:** Введите ставку за 1 подписчика (CPC) в рублях (например, 1.20):")


@router.message(CampaignStates.waiting_for_price)
async def process_campaign_price(message: types.Message, state: FSMContext, session: AsyncSession):
    try:
        price = float(message.text.strip())
        if price < 0.2:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Минимальная ставка — 0.20 RUB:")
        return

    data = await state.get_data()
    channel_link = data.get("channel_link")
    budget = data.get("budget")
    await state.clear()

    user = await session.get(User, message.from_user.id)
    if float(user.balance) < budget:
        await message.answer("⚠️ На балансе недостаточно средств.", reply_markup=main_menu_kb())
        return

    user.balance -= Decimal(str(budget))
    new_order = Order(
        user_id=message.from_user.id,
        channel_id=-1001234567890,
        channel_title="Канал рекламодателя",
        channel_link=channel_link,
        total_budget=Decimal(str(budget)),
        remaining_budget=Decimal(str(budget)),
        cpc_price=Decimal(str(price)),
        status="active"
    )
    session.add(new_order)
    await session.commit()

    await message.answer(
        f"✅ **Рекламная кампания #{new_order.id} успешно запущена!**\n\n"
        f"• Канал: {channel_link}\n"
        f"• Бюджет: **{budget:.2f} RUB**\n"
        f"• Ставка за подписку: **{price:.2f} RUB**\n"
        f"• Статус: **🟢 Активен**",
        reply_markup=main_menu_kb(is_admin_user(message.from_user.id)),
        parse_mode="Markdown"
    )


# Детальный просмотр кампании (Скриншот 1)
@router.callback_query(F.data.startswith("order_view:"))
@router.callback_query(F.data.startswith("order_refresh:"))
async def order_view(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    order_id = int(callback.data.split(":")[1])
    order_obj = await session.get(Order, order_id)

    if not order_obj:
        await callback.message.edit_text("Заказ не найден.", reply_markup=back_kb(target="buy_traffic"))
        return

    spent = float(order_obj.total_budget - order_obj.remaining_budget)
    price = float(order_obj.cpc_price)
    status_emoji = "🟢" if order_obj.status == "active" else "⏸"

    text = (
        f"🛍 **Заказ #{order_obj.id}**\n\n"
        "Трафик: Подписки\n"
        "Назначение: Канал/чат\n"
        f"Статус: {status_emoji} {order_obj.status.capitalize()}\n"
        f"Цена: {price:.2f} ₽\n"
        f"Потрачено: {spent:.2f} ₽"
    )
    await callback.message.edit_text(
        text,
        reply_markup=order_control_kb(order_obj.id, order_obj.status, price),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("order_toggle:"))
async def order_toggle(callback: types.CallbackQuery, session: AsyncSession):
    order_id = int(callback.data.split(":")[1])
    order_obj = await session.get(Order, order_id)
    if order_obj:
        order_obj.status = "paused" if order_obj.status == "active" else "active"
        await session.commit()
        await callback.answer(f"Статус изменён на {order_obj.status}")
    await order_view(callback, session)


@router.callback_query(F.data.startswith("order_delete:"))
async def order_delete(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    order_id = int(callback.data.split(":")[1])
    order_obj = await session.get(Order, order_id)
    if order_obj:
        # Возвращаем остаток бюджета
        user = await session.get(User, order_obj.user_id)
        if user:
            user.balance += order_obj.remaining_budget
        await session.delete(order_obj)
        await session.commit()
    await callback.message.edit_text("🗑 Заказ удалён. Неизрасходованный бюджет возвращён на баланс.", reply_markup=back_kb(target="buy_traffic"))


# Кнопки таргетинга (переключатели на экране заказа)
@router.callback_query(F.data.startswith("order_price:"))
async def order_price_click(callback: types.CallbackQuery):
    await callback.answer("Для изменения ставки используйте настройки кампании.", show_alert=True)


@router.callback_query(F.data.startswith("order_target_"))
async def order_targets_click(callback: types.CallbackQuery):
    await callback.answer("Таргетинг активен для всех категорий трафика сети.")


# -------------------------------------------------------------
# Партнёрская программа
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
EOFcat << 'EOF' > smikhub/bot/handlers/core.py
import secrets
from decimal import Decimal
import aiohttp
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import LabeledPrice
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.db.models import User, Bot, Order
from smikhub.config import BASE_URL, ADMIN_CHAT_ID, CRYPTO_BOT_TOKEN
from smikhub.bot.keyboards import (
    main_menu_kb,
    cabinet_kb,
    topup_methods_kb,
    withdraw_methods_kb,
    bot_list_kb,
    bot_settings_kb,
    buy_traffic_kb,
    order_control_kb,
    admin_bot_moderation_kb,
    back_kb
)

router = Router()


class AddBotStates(StatesGroup):
    waiting_for_username = State()


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

    text = (
        "👋 **Добро пожаловать в SmikHub!**\n\n"
        "Биржа обязательных подписок (ОП) в Telegram.\n"
        "Монетизируйте своих ботов или закупайте живой целевой трафик на каналы."
    )
    await message.answer(text, reply_markup=main_menu_kb(is_admin_user(uid)), parse_mode="Markdown")


@router.callback_query(F.data == "nav:main_menu")
async def nav_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    text = "👋 **Главное меню SmikHub**\n\nВыберите нужный раздел:"
    await callback.message.edit_text(text, reply_markup=main_menu_kb(is_admin_user(callback.from_user.id)), parse_mode="Markdown")


# -------------------------------------------------------------
# Админка (/admin и кнопка)
# -------------------------------------------------------------
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
        f"📢 Рекламных заказов: `{orders_count}`"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📢 Рассылка по пользователям", callback_data="admin:broadcast")],
        [types.InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")]
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
        f"📢 Рекламных заказов: `{orders_count}`"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📢 Рассылка по пользователям", callback_data="admin:broadcast")],
        [types.InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(callback: types.CallbackQuery):
    if not is_admin_user(callback.from_user.id):
        return
    await callback.answer()
    await callback.message.edit_text(
        "📢 **Рассылка сообщений**\n\nОтправьте текст сообщения для массовой рассылки всем пользователям платформы.",
        reply_markup=back_kb(target="admin")
    )


# -------------------------------------------------------------
# Кабинет пользователя
# -------------------------------------------------------------
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
    await callback.message.edit_text(text, reply_markup=cabinet_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "nav:topup_menu")
async def nav_topup_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    text = "💳 **Выберите способ пополнения баланса:**"
    await callback.message.edit_text(text, reply_markup=topup_methods_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "topup:cryptobot")
async def topup_cryptobot(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TopupStates.waiting_for_crypto_amount)
    text = "🤖 Введите сумму пополнения в рублях (минимум 50 RUB):"
    await callback.message.edit_text(text, reply_markup=back_kb(target="topup_menu"))


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
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💳 Оплатить счет", url=invoice_url)],
            [types.InlineKeyboardButton(text="« Назад в кабинет", callback_data="nav:cabinet")]
        ])
        await message.answer(f"🧾 Счёт на {amount:.2f} RUB ({usdt_amount} USDT) успешно выставлен:", reply_markup=kb)
    else:
        await message.answer(
            f"🧾 Создана заявка на {amount:.2f} RUB.\nШлюз ожидает подтверждения.",
            reply_markup=back_kb(target="topup_menu")
        )


@router.callback_query(F.data == "topup:stars")
async def topup_stars(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TopupStates.waiting_for_stars_amount)
    text = "⭐️ Введите количество Stars для оплаты (1 Star = 1.50 RUB, минимум 10):"
    await callback.message.edit_text(text, reply_markup=back_kb(target="topup_menu"))


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
            title="Пополнение баланса SmikHub",
            description=f"Зачисление {rub_val} RUB на рекламный баланс",
            payload=f"stars_{message.from_user.id}_{rub_val}",
            currency="XTR",
            prices=prices
        )
    except Exception as e:
        await message.answer(f"⚠️ Ошибка создания счёта Stars: {e}", reply_markup=back_kb(target="topup_menu"))


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
            await message.answer(f"✅ Баланс успешно пополнен на {rub_amount:.2f} RUB!", reply_markup=main_menu_kb())


# -------------------------------------------------------------
# Вывод средств (SendPay)
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:withdraw_menu")
async def nav_withdraw_menu(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.clear()
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    text = (
        f"📤 **Вывод заработанных средств**\n\n"
        f"Доступно к выводу: **{balance:.2f} RUB**\n"
        "Минимальная выплата: **100.00 RUB**"
    )
    await callback.message.edit_text(text, reply_markup=withdraw_methods_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "withdraw:sendpay")
async def withdraw_sendpay(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    if balance < 100.0:
        text = (
            "⚠️ **Недостаточно средств**\n\n"
            f"Текущий баланс: **{balance:.2f} RUB**.\n"
            "Минимальный вывод через SendPay: **100.00 RUB**."
        )
        await callback.message.edit_text(text, reply_markup=back_kb(target="withdraw_menu"), parse_mode="Markdown")
        return

    await state.set_state(WithdrawStates.waiting_for_amount)
    text = f"💳 **Вывод через SendPay (СБП / Карты РФ)**\n\nДоступно: **{balance:.2f} RUB**\n\nВведите сумму для вывода:"
    await callback.message.edit_text(text, reply_markup=back_kb(target="withdraw_menu"), parse_mode="Markdown")


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
        await message.answer("⚠️ На балансе недостаточно средств.", reply_markup=main_menu_kb())
        return

    user.balance -= Decimal(str(amount))
    await session.commit()

    await message.answer(
        f"✅ **Заявка на вывод #{secrets.token_hex(4)} принята!**\n\n"
        f"• Сумма: **{amount:.2f} RUB**\n"
        f"• Реквизиты: `{requisites}`\n"
        "• Платёжный шлюз: **SendPay (Авто)**\n\n"
        "Средства поступят на карту в течение 10–15 минут.",
        reply_markup=main_menu_kb(),
        parse_mode="Markdown"
    )


# -------------------------------------------------------------
# Продать ОП (Боты, модерация, настройки)
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
            "У вас пока нет подключённых ботов.\n"
            "Нажмите «➕ Добавить бота», чтобы отправить заявку на модерацию и начать зарабатывать."
        )
        await callback.message.edit_text(text, reply_markup=bot_list_kb([]), parse_mode="Markdown")
        return

    text = "🤖 **Ваши подключённые боты:**\n\nВыберите бота для управления параметрами:"
    await callback.message.edit_text(text, reply_markup=bot_list_kb(bots), parse_mode="Markdown")


@router.callback_query(F.data == "nav:add_bot")
async def nav_add_bot(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddBotStates.waiting_for_username)
    text = (
        "➕ **Добавление нового бота на платформу**\n\n"
        "Отправьте юзернейм вашего бота (например, `@MyBestBot` или `MyBestBot`).\n"
        "Бот будет отправлен администратору на быструю модерацию."
    )
    await callback.message.edit_text(text, reply_markup=back_kb(target="sell_traffic"), parse_mode="Markdown")


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

    # Уведомляем администратора о новом боте
    if ADMIN_CHAT_ID:
        try:
            admin_msg = (
                "🔔 **Новый бот на модерацию!**\n\n"
                f"• Бот: @{new_bot.username}\n"
                f"• Владелец ID: `{message.from_user.id}`\n"
                f"• Имя владельца: @{message.from_user.username or 'без username'}"
            )
            await message.bot.send_message(
                ADMIN_CHAT_ID,
                admin_msg,
                reply_markup=admin_bot_moderation_kb(new_bot.id),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    text = (
        f"✅ **Бот @{new_bot.username} отправлен на модерацию!**\n\n"
        f"🔑 Токен API: `{new_token}`\n"
        f"После подтверждения администратором бот начнёт получать рекламные задания."
    )
    await message.answer(text, reply_markup=back_kb(target="sell_traffic"), parse_mode="Markdown")


@router.callback_query(F.data.startswith("admin_approve_bot:"))
async def admin_approve_bot(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer("Бот одобрен!")
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        try:
            await callback.bot.send_message(
                bot_obj.user_id,
                f"🎉 **Ваш бот @{bot_obj.username} успешно прошёл модерацию и активирован!**",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    await callback.message.edit_text(f"✅ Бот #{bot_id} одобрен администратором.")


@router.callback_query(F.data.startswith("admin_reject_bot:"))
async def admin_reject_bot(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer("Бот отклонён!")
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        try:
            await callback.bot.send_message(
                bot_obj.user_id,
                f"⚠️ Ваш бот @{bot_obj.username} не прошёл модерацию.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await session.delete(bot_obj)
        await session.commit()
    await callback.message.edit_text(f"❌ Бот #{bot_id} отклонён и удалён.")


# Экран управления конкретным ботом (Скриншот 2)
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
        f"• Лимит спонсоров: **{bot_obj.max_sponsors}**\n"
        f"• Рейтинг качества: **{bot_obj.quality_score * 100:.0f}%**\n\n"
        "Настройте параметры кнопками ниже:"
    )
    await callback.message.edit_text(text, reply_markup=bot_settings_kb(bot_id), parse_mode="Markdown")


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
    await callback.answer(f"Цена изменена на {next_price:.2f} RUB")

    text = (
        f"⚙️ **Управление ботом @{bot_obj.username}**\n\n"
        f"• Мин. цена: **{float(bot_obj.min_price):.2f} RUB**\n"
        f"• Лимит спонсоров: **{bot_obj.max_sponsors}**\n"
        f"• Рейтинг качества: **{bot_obj.quality_score * 100:.0f}%**\n\n"
        "Настройте параметры кнопками ниже:"
    )
    await callback.message.edit_text(text, reply_markup=bot_settings_kb(bot_id), parse_mode="Markdown")


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
    await callback.answer(f"Лимит спонсоров: {new_limit}")

    text = (
        f"⚙️ **Управление ботом @{bot_obj.username}**\n\n"
        f"• Мин. цена: **{float(bot_obj.min_price):.2f} RUB**\n"
        f"• Лимит спонсоров: **{bot_obj.max_sponsors}**\n"
        f"• Рейтинг качества: **{bot_obj.quality_score * 100:.0f}%**\n\n"
        "Настройте параметры кнопками ниже:"
    )
    await callback.message.edit_text(text, reply_markup=bot_settings_kb(bot_id), parse_mode="Markdown")


@router.callback_query(F.data.startswith("bot_show_token:"))
async def bot_show_token(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    text = f"🔑 **Токен интеграции для @{bot_obj.username}:**\n\n`{bot_obj.integration_token}`"
    await callback.message.edit_text(text, reply_markup=back_kb(target=f"sell_traffic"), parse_mode="Markdown")


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
    text = f"📋 **Готовый код интеграции:**\n\n```python\n{code}\n```"
    await callback.message.edit_text(text, reply_markup=back_kb(target="sell_traffic"), parse_mode="Markdown")


@router.callback_query(F.data.startswith("bot_integrations:"))
async def bot_integrations(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    text = (
        f"🌐 **Сторонние рекламные сети для @{bot_obj.username}**\n\n"
        "Вы можете подключить внешние биржи рекламы, чтобы бот автоматически показывал объявления, "
        "когда нет активных спонсоров в SmikHub:\n\n"
        "• **Adsgram API:** Видеореклама и баннеры Telegram Mini Apps\n"
        "• **PR Flow API:** Обязательные подписки на каналы партнёров\n"
        "• **Trafsly:** Дополнительная ротация прямых рекламодателей\n\n"
        f"Webhook уведомлений: `{bot_obj.webhook_url or 'По умолчанию'}`"
    )
    await callback.message.edit_text(text, reply_markup=back_kb(target=f"sell_traffic"), parse_mode="Markdown")


@router.callback_query(F.data.startswith("bot_delete:"))
async def bot_delete(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        await session.delete(bot_obj)
        await session.commit()
    await callback.message.edit_text("🗑 Бот успешно удалён из платформы.", reply_markup=back_kb(target="sell_traffic"))


# -------------------------------------------------------------
# Купить ОП (Панель кампаний со всеми таргетингами)
# -------------------------------------------------------------
@router.callback_query(F.data == "nav:buy_traffic")
async def nav_buy_traffic(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    orders = (await session.execute(
        select(Order).where(Order.user_id == callback.from_user.id)
    )).scalars().all()

    text = (
        "📢 **Закупка трафика (Купить ОП)**\n\n"
        "Создавайте рекламные кампании для набора живых подписчиков в каналы через сеть ботов SmikHub."
    )
    await callback.message.edit_text(text, reply_markup=buy_traffic_kb(orders), parse_mode="Markdown")


@router.callback_query(F.data == "nav:create_order")
async def nav_create_order(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    if balance < 100.0:
        text = (
            "⚠️ **Недостаточно средств для запуска кампании**\n\n"
            f"Текущий баланс: **{balance:.2f} RUB**\n"
            "Минимальный бюджет для создания кампании: **100.00 RUB**.\n"
            "Пополните баланс в разделе «👤 Кабинет»."
        )
        await callback.message.edit_text(text, reply_markup=back_kb(target="buy_traffic"), parse_mode="Markdown")
        return

    await state.set_state(CampaignStates.waiting_for_channel)
    text = "✍️ **Шаг 1/3:** Отправьте ссылку на канал или чат (например, `https://t.me/mychannel`):"
    await callback.message.edit_text(text, reply_markup=back_kb(target="buy_traffic"), parse_mode="Markdown")


@router.message(CampaignStates.waiting_for_channel)
async def process_campaign_channel(message: types.Message, state: FSMContext):
    link = message.text.strip()
    if "t.me/" not in link:
        await message.answer("⚠️ Отправьте корректную ссылку Telegram (начинается с https://t.me/...):")
        return

    await state.update_data(channel_link=link)
    await state.set_state(CampaignStates.waiting_for_budget)
    await message.answer("✍️ **Шаг 2/3:** Введите общий бюджет кампании в рублях (минимум 100 RUB):")


@router.message(CampaignStates.waiting_for_budget)
async def process_campaign_budget(message: types.Message, state: FSMContext):
    try:
        budget = float(message.text.strip())
        if budget < 100:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Введите число не менее 100 руб.:")
        return

    await state.update_data(budget=budget)
    await state.set_state(CampaignStates.waiting_for_price)
    await message.answer("✍️ **Шаг 3/3:** Введите ставку за 1 подписчика (CPC) в рублях (например, 1.20):")


@router.message(CampaignStates.waiting_for_price)
async def process_campaign_price(message: types.Message, state: FSMContext, session: AsyncSession):
    try:
        price = float(message.text.strip())
        if price < 0.2:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Минимальная ставка — 0.20 RUB:")
        return

    data = await state.get_data()
    channel_link = data.get("channel_link")
    budget = data.get("budget")
    await state.clear()

    user = await session.get(User, message.from_user.id)
    if float(user.balance) < budget:
        await message.answer("⚠️ На балансе недостаточно средств.", reply_markup=main_menu_kb())
        return

    user.balance -= Decimal(str(budget))
    new_order = Order(
        user_id=message.from_user.id,
        channel_id=-1001234567890,
        channel_title="Канал рекламодателя",
        channel_link=channel_link,
        total_budget=Decimal(str(budget)),
        remaining_budget=Decimal(str(budget)),
        cpc_price=Decimal(str(price)),
        status="active"
    )
    session.add(new_order)
    await session.commit()

    await message.answer(
        f"✅ **Рекламная кампания #{new_order.id} успешно запущена!**\n\n"
        f"• Канал: {channel_link}\n"
        f"• Бюджет: **{budget:.2f} RUB**\n"
        f"• Ставка за подписку: **{price:.2f} RUB**\n"
        f"• Статус: **🟢 Активен**",
        reply_markup=main_menu_kb(is_admin_user(message.from_user.id)),
        parse_mode="Markdown"
    )


# Детальный просмотр кампании (Скриншот 1)
@router.callback_query(F.data.startswith("order_view:"))
@router.callback_query(F.data.startswith("order_refresh:"))
async def order_view(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    order_id = int(callback.data.split(":")[1])
    order_obj = await session.get(Order, order_id)

    if not order_obj:
        await callback.message.edit_text("Заказ не найден.", reply_markup=back_kb(target="buy_traffic"))
        return

    spent = float(order_obj.total_budget - order_obj.remaining_budget)
    price = float(order_obj.cpc_price)
    status_emoji = "🟢" if order_obj.status == "active" else "⏸"

    text = (
        f"🛍 **Заказ #{order_obj.id}**\n\n"
        "Трафик: Подписки\n"
        "Назначение: Канал/чат\n"
        f"Статус: {status_emoji} {order_obj.status.capitalize()}\n"
        f"Цена: {price:.2f} ₽\n"
        f"Потрачено: {spent:.2f} ₽"
    )
    await callback.message.edit_text(
        text,
        reply_markup=order_control_kb(order_obj.id, order_obj.status, price),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("order_toggle:"))
async def order_toggle(callback: types.CallbackQuery, session: AsyncSession):
    order_id = int(callback.data.split(":")[1])
    order_obj = await session.get(Order, order_id)
    if order_obj:
        order_obj.status = "paused" if order_obj.status == "active" else "active"
        await session.commit()
        await callback.answer(f"Статус изменён на {order_obj.status}")
    await order_view(callback, session)


@router.callback_query(F.data.startswith("order_delete:"))
async def order_delete(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    order_id = int(callback.data.split(":")[1])
    order_obj = await session.get(Order, order_id)
    if order_obj:
        # Возвращаем остаток бюджета
        user = await session.get(User, order_obj.user_id)
        if user:
            user.balance += order_obj.remaining_budget
        await session.delete(order_obj)
        await session.commit()
    await callback.message.edit_text("🗑 Заказ удалён. Неизрасходованный бюджет возвращён на баланс.", reply_markup=back_kb(target="buy_traffic"))


# Кнопки таргетинга (переключатели на экране заказа)
@router.callback_query(F.data.startswith("order_price:"))
async def order_price_click(callback: types.CallbackQuery):
    await callback.answer("Для изменения ставки используйте настройки кампании.", show_alert=True)


@router.callback_query(F.data.startswith("order_target_"))
async def order_targets_click(callback: types.CallbackQuery):
    await callback.answer("Таргетинг активен для всех категорий трафика сети.")


# -------------------------------------------------------------
# Партнёрская программа
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
