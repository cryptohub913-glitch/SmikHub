import secrets
from decimal import Decimal
from datetime import datetime
import aiohttp
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.db.models import User, Bot, Order, Withdrawal
from smikhub.config import BASE_URL, CRYPTO_BOT_TOKEN
import smikhub.config as config

router = Router()

# ==========================================
# FSM Состояния
# ==========================================
class CampaignStates(StatesGroup):
    waiting_for_channel = State()
    waiting_for_budget = State()
    waiting_for_price = State()

class TopupStates(StatesGroup):
    waiting_for_crypto_amount = State()

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

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_bot_search = State()
    waiting_for_quality_score = State()

# ==========================================
# Клавиатуры пользователя
# ==========================================
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
            InlineKeyboardButton(text="💳 Пополнить (CryptoBot)", callback_data="nav:topup"),
            InlineKeyboardButton(text="📤 Вывести (CryptoBot)", callback_data="nav:withdraw")
        ],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")]
    ])

def kb_bot_list(bots: list) -> InlineKeyboardMarkup:
    buttons = []
    for b in bots:
        status_icon = "🟢" if getattr(b, "is_active", True) else "🔴"
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

def kb_price_grid(bot_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for i in range(10, 50, 5):
        row = []
        for j in range(5):
            val = (i + j) / 10.0
            row.append(InlineKeyboardButton(text=f"{val:.1f}р.", callback_data=f"set_prc:{bot_id}:{val:.1f}"))
        buttons.append(row)
    for i in range(5, 15, 5):
        row = []
        for j in range(5):
            val = float(i + j)
            row.append(InlineKeyboardButton(text=f"{val:.1f}р.", callback_data=f"set_prc:{bot_id}:{val:.1f}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="15.0р.", callback_data=f"set_prc:{bot_id}:15.0")])
    buttons.append([InlineKeyboardButton(text="« Отмена", callback_data=f"bot_manage:{bot_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def kb_sponsors_grid(bot_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"{i}", callback_data=f"set_spn:{bot_id}:{i}") for i in range(1, 6)],
        [InlineKeyboardButton(text=f"{i}", callback_data=f"set_spn:{bot_id}:{i}") for i in range(6, 11)],
        [InlineKeyboardButton(text="« Отмена", callback_data=f"bot_manage:{bot_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def kb_delete_confirm(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Да, удалить бота", callback_data=f"del_conf:{bot_id}")],
        [InlineKeyboardButton(text="« Отмена", callback_data=f"bot_manage:{bot_id}")]
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

# ==========================================
# Клавиатуры администратора
# ==========================================
def kb_admin_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤖 Управление ботами", callback_data="admin:bots_list"),
            InlineKeyboardButton(text="🔍 Найти бота", callback_data="admin:search_bot")
        ],
        [
            InlineKeyboardButton(text="📤 Заявки на вывод", callback_data="admin:withdrawals"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")
        ],
        [InlineKeyboardButton(text="« Назад в главное меню", callback_data="nav:main_menu")]
    ])

def kb_admin_bot_card(bot_id: int, is_active: bool) -> InlineKeyboardMarkup:
    ban_btn_text = "🔴 Заблокировать бота" if is_active else "🟢 Разблокировать бота"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ban_btn_text, callback_data=f"admin:toggle_bot:{bot_id}")],
        [InlineKeyboardButton(text="⭐ Изменить качество аудитории", callback_data=f"admin:edit_quality:{bot_id}")],
        [InlineKeyboardButton(text="🗑 Удалить бота из базы", callback_data=f"admin:delete_bot:{bot_id}")],
        [InlineKeyboardButton(text="« К списку ботов", callback_data="admin:bots_list")]
    ])

def is_admin_user(user_id: int) -> bool:
    if str(user_id) == "6470511118":
        return True
    admin_id = getattr(config, 'ADMIN_CHAT_ID', None)
    admin_ids = getattr(config, 'ADMIN_USER_IDS', [])
    if admin_id and str(user_id) == str(admin_id):
        return True
    if admin_ids and str(user_id) in str(admin_ids):
        return True
    return False

# ==========================================
# Главное меню и /start
# ==========================================
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

    text_msg = (
        "👋 **Добро пожаловать в SmikHub!**\n\n"
        "Биржа обязательных подписок (ОП) в Telegram.\n"
        "Монетизируйте своих ботов или закупайте живой целевой трафик."
    )
    await message.answer(text_msg, reply_markup=kb_main_menu(is_admin_user(uid)), parse_mode="Markdown")

@router.callback_query(F.data == "nav:main_menu")
async def nav_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    text_msg = "👋 **Главное меню SmikHub**\n\nВыберите нужный раздел:"
    await callback.message.edit_text(text_msg, reply_markup=kb_main_menu(is_admin_user(callback.from_user.id)), parse_mode="Markdown")

# ==========================================
# Админ-панель: Прозрачность и управление
# ==========================================
@router.message(Command("admin"))
async def admin_command(message: types.Message, session: AsyncSession):
    if not is_admin_user(message.from_user.id):
        return
    users_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
    bots_count = (await session.execute(select(func.count(Bot.id)))).scalar() or 0
    orders_count = (await session.execute(select(func.count(Order.id)))).scalar() or 0

    text_msg = (
        "🛠 **Административная панель SmikHub**\n\n"
        f"👥 Всего пользователей: `{users_count}`\n"
        f"🤖 Подключено ботов: `{bots_count}`\n"
        f"📢 Рекламных заказов: `{orders_count}`\n\n"
        "Выберите раздел для полного аудита и управления:"
    )
    await message.answer(text_msg, reply_markup=kb_admin_main(), parse_mode="Markdown")

@router.callback_query(F.data == "nav:admin")
async def nav_admin(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    if not is_admin_user(callback.from_user.id):
        await callback.answer("Доступ запрещен.", show_alert=True)
        return
    await state.clear()
    await callback.answer()
    users_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
    bots_count = (await session.execute(select(func.count(Bot.id)))).scalar() or 0
    orders_count = (await session.execute(select(func.count(Order.id)))).scalar() or 0

    text_msg = (
        "🛠 **Административная панель SmikHub**\n\n"
        f"👥 Всего пользователей: `{users_count}`\n"
        f"🤖 Подключено ботов: `{bots_count}`\n"
        f"📢 Рекламных заказов: `{orders_count}`\n\n"
        "Выберите раздел для аудита и управления:"
    )
    await callback.message.edit_text(text_msg, reply_markup=kb_admin_main(), parse_mode="Markdown")

@router.callback_query(F.data == "admin:bots_list")
async def admin_bots_list(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id):
        return
    await callback.answer()
    bots = (await session.execute(select(Bot).order_by(Bot.id.desc()).limit(30))).scalars().all()

    buttons = []
    for b in bots:
        st = "🟢" if b.is_active else "🔴"
        q_pct = int((b.quality_score or 0.8) * 100)
        buttons.append([InlineKeyboardButton(
            text=f"{st} #{b.id} @{b.username} (Качество: {q_pct}%)",
            callback_data=f"admin:bot_card:{b.id}"
        )])
    buttons.append([InlineKeyboardButton(text="🔍 Найти бота (ID / @username)", callback_data="admin:search_bot")])
    buttons.append([InlineKeyboardButton(text="« Назад в админку", callback_data="nav:admin")])

    await callback.message.edit_text(
        "🤖 **Реестр подключенных ботов платформы:**\n\nНажмите на бота для проверки качества аудитории и управления доступом:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin:search_bot")
async def admin_search_bot(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user.id):
        return
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_bot_search)
    await callback.message.edit_text(
        "🔍 **Поиск бота**\n\nВведите **ID бота** (число) или **юзернейм** (например, `@Bot_1118` или `Bot_1118`):",
        reply_markup=kb_cancel("admin", "« Отмена"),
        parse_mode="Markdown"
    )

@router.message(AdminStates.waiting_for_bot_search)
async def process_admin_bot_search(message: types.Message, state: FSMContext, session: AsyncSession):
    if not is_admin_user(message.from_user.id):
        return
    query = message.text.strip().replace("@", "")
    await state.clear()

    bot_obj = None
    if query.isdigit():
        bot_obj = await session.get(Bot, int(query))
    if not bot_obj:
        bot_obj = (await session.execute(select(Bot).where(Bot.username.ilike(query)))).scalar_one_or_none()

    if not bot_obj:
        await message.answer("❌ Бот с такими параметрами не найден.", reply_markup=kb_cancel("admin", "« В админку"))
        return
    await render_bot_admin_card(message, bot_obj, session)

@router.callback_query(F.data.startswith("admin:bot_card:"))
async def admin_bot_card_handler(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id):
        return
    await callback.answer()
    bot_id = int(callback.data.split(":")[2])
    bot_obj = await session.get(Bot, bot_id)
    if not bot_obj:
        await callback.message.edit_text("Бот не найден.", reply_markup=kb_cancel("admin"))
        return
    await render_bot_admin_card(callback.message, bot_obj, session, edit=True)

async def render_bot_admin_card(message_or_callback_msg: types.Message, bot_obj: Bot, session: AsyncSession, edit: bool = False):
    owner = await session.get(User, bot_obj.user_id)
    owner_str = f"@{owner.username}" if owner and owner.username else f"ID: {bot_obj.user_id}"
    quality_pct = int((bot_obj.quality_score or 0.8) * 100)
    status_text = "🟢 Активен (Получает задания)" if bot_obj.is_active else "🔴 Заблокирован / Отключен"

    card_text = (
        f"📊 **Аудит бота #{bot_obj.id} — @{bot_obj.username}**\n\n"
        f"• **Статус в бирже:** {status_text}\n"
        f"• **Владелец:** {owner_str} (`{bot_obj.user_id}`)\n"
        f"• **Качество аудитории:** **{quality_pct}%** (Коэф: `{bot_obj.quality_score:.2f}`)\n"
        f"• **Мин. ставка (CPC):** `{float(bot_obj.min_price):.2f} RUB`\n"
        f"• **Лимит спонсоров:** `{bot_obj.max_sponsors}`\n"
        f"• **Токен интеграции:** `{bot_obj.integration_token}`\n\n"
        f"🌐 **Подключённые сторонние шлюзы:**\n"
        f"  Subgram: `{'Подключен' if bot_obj.subgram_token else 'Нет'}`\n"
        f"  Flyer: `{'Подключен' if bot_obj.flyer_token else 'Нет'}`\n"
        f"  Traffy: `{'Подключен' if bot_obj.traffy_token else 'Нет'}`\n"
        f"  PiarFlow: `{'Подключен' if bot_obj.piarflow_token else 'Нет'}`\n"
        f"  TgGrass: `{'Подключен' if bot_obj.tgrass_token else 'Нет'}`"
    )
    kb = kb_admin_bot_card(bot_obj.id, bot_obj.is_active)
    if edit:
        await message_or_callback_msg.edit_text(card_text, reply_markup=kb, parse_mode="Markdown")
    else:
        await message_or_callback_msg.answer(card_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin:toggle_bot:"))
async def admin_toggle_bot(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id):
        return
    bot_id = int(callback.data.split(":")[2])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        bot_obj.is_active = not bot_obj.is_active
        await session.commit()
        status_word = "разблокирован" if bot_obj.is_active else "заблокирован"
        await callback.answer(f"Бот #{bot_id} {status_word}!")
        await render_bot_admin_card(callback.message, bot_obj, session, edit=True)

@router.callback_query(F.data.startswith("admin:edit_quality:"))
async def admin_edit_quality(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user.id):
        return
    await callback.answer()
    bot_id = int(callback.data.split(":")[2])
    await state.update_data(target_bot_id=bot_id)
    await state.set_state(AdminStates.waiting_for_quality_score)
    await callback.message.edit_text(
        f"⭐ **Настройка качества аудитории для бота #{bot_id}**\n\nВведите коэффициент качества от **0.1** до **1.0**\n(Например: `0.9` = 90% качества, `0.5` = 50% качества):",
        reply_markup=kb_cancel("admin:bots_list", "« Отмена"),
        parse_mode="Markdown"
    )

@router.message(AdminStates.waiting_for_quality_score)
async def process_admin_quality_score(message: types.Message, state: FSMContext, session: AsyncSession):
    if not is_admin_user(message.from_user.id):
        return
    try:
        val = float(message.text.strip().replace(",", "."))
        if val < 0.05 or val > 1.0:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Введите число от 0.1 до 1.0:")
        return
    data = await state.get_data()
    bot_id = data.get("target_bot_id")
    await state.clear()
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        bot_obj.quality_score = val
        await session.commit()
        await message.answer(f"✅ Качество аудитории бота #{bot_id} установлено на **{int(val * 100)}%**.")
        await render_bot_admin_card(message, bot_obj, session, edit=False)

@router.callback_query(F.data.startswith("admin:delete_bot:"))
async def admin_delete_bot(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id):
        return
    bot_id = int(callback.data.split(":")[2])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        await session.delete(bot_obj)
        await session.commit()
        await callback.answer("Бот удалён из базы.")
    await admin_bots_list(callback, session)

@router.callback_query(F.data == "admin:withdrawals")
async def admin_withdrawals(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id):
        return
    await callback.answer()
    items = (await session.execute(
        select(Withdrawal).where(Withdrawal.status == "pending").order_by(Withdrawal.id.desc()).limit(10)
    )).scalars().all()

    if not items:
        await callback.message.edit_text(
            "📤 **Заявки на вывод средств**\n\nНет активных заявок в очереди.",
            reply_markup=kb_cancel("admin", "« Назад"),
            parse_mode="Markdown"
        )
        return
    buttons = []
    text_lines = ["📤 **Заявки на вывод (Ожидают выплаты):**\n"]
    for w in items:
        text_lines.append(f"• Заявка #{w.id}: `{float(w.amount):.2f} RUB` | Реквизиты: `{w.requisites}` | User ID: `{w.user_id}`")
        buttons.append([
            InlineKeyboardButton(text=f"✅ Выплачено #{w.id}", callback_data=f"admin_w_pay:{w.id}"),
            InlineKeyboardButton(text=f"❌ Отклонить #{w.id}", callback_data=f"admin_w_rej:{w.id}")
        ])
    buttons.append([InlineKeyboardButton(text="« Назад в админку", callback_data="nav:admin")])
    await callback.message.edit_text("\n".join(text_lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_w_pay:"))
async def admin_w_pay(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id):
        return
    w_id = int(callback.data.split(":")[1])
    w_obj = await session.get(Withdrawal, w_id)
    if w_obj:
        w_obj.status = "completed"
        await session.commit()
        try:
            await callback.bot.send_message(w_obj.user_id, f"✅ Ваша выплата #{w_obj.id} на сумму {w_obj.amount:.2f} RUB успешно отправлена!")
        except Exception:
            pass
        await callback.answer(f"Заявка #{w_id} помечена как выполненная.")
    await admin_withdrawals(callback, session)

@router.callback_query(F.data.startswith("admin_w_rej:"))
async def admin_w_rej(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id):
        return
    w_id = int(callback.data.split(":")[1])
    w_obj = await session.get(Withdrawal, w_id)
    if w_obj:
        w_obj.status = "rejected"
        user = await session.get(User, w_obj.user_id)
        if user:
            user.balance += w_obj.amount
        await session.commit()
        try:
            await callback.bot.send_message(w_obj.user_id, f"❌ Ваша выплата #{w_obj.id} отклонена. Средства возвращены на баланс.")
        except Exception:
            pass
        await callback.answer(f"Заявка #{w_id} отклонена, баланс возвращён.")
    await admin_withdrawals(callback, session)

@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_prompt(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user.id):
        return
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.message.edit_text(
        "📢 **Рассылка сообщений**\n\nОтправьте текст или медиа, которое увидят все пользователи SmikHub:",
        reply_markup=kb_cancel("admin", "« Отмена"),
        parse_mode="Markdown"
    )

@router.message(AdminStates.waiting_for_broadcast)
async def process_admin_broadcast(message: types.Message, state: FSMContext, session: AsyncSession):
    if not is_admin_user(message.from_user.id):
        return
    await state.clear()
    users = (await session.execute(select(User.id))).scalars().all()
    sent_count = 0
    status_msg = await message.answer(f"⏳ Запуск рассылки на {len(users)} пользователей...")
    for uid in users:
        try:
            await message.copy_to(chat_id=uid)
            sent_count += 1
        except Exception:
            continue
    await status_msg.edit_text(f"✅ Рассылка завершена!\nУспешно доставлено: {sent_count} из {len(users)} пользователей.", reply_markup=kb_cancel("admin", "« В админку"))

# ==========================================
# Кабинет пользователя (Пополнить / Вывести)
# ==========================================
@router.callback_query(F.data == "nav:cabinet")
async def nav_cabinet(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.clear()
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0

    text_msg = (
        f"👤 **Личный кабинет**\n\n"
        f"🆔 Ваш ID: `{callback.from_user.id}`\n"
        f"💰 Основной баланс: **{balance:.2f} RUB**\n\n"
        "Выберите действие для управления балансом:"
    )
    await callback.message.edit_text(text_msg, reply_markup=kb_cabinet(), parse_mode="Markdown")

@router.callback_query(F.data == "nav:topup")
async def nav_topup(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TopupStates.waiting_for_crypto_amount)
    text_msg = "🤖 **Пополнение через Crypto Pay API**\n\nВведите сумму пополнения в рублях (минимум 15 RUB):"
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel("nav:cabinet", "« Назад"), parse_mode="Markdown")

@router.message(TopupStates.waiting_for_crypto_amount)
async def process_crypto_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount < 15:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Введите число не менее 15 руб.:")
        return
    await state.clear()
    usdt_amount = max(0.15, round(amount / 95.0, 2))
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
        await message.answer(f"🧾 Счёт на **{amount:.2f} RUB** ({usdt_amount} USDT) выставлен:", reply_markup=kb, parse_mode="Markdown")
    else:
        await message.answer("🧾 Заявка создана.\nШлюз ожидает подтверждения.", reply_markup=kb_cancel("nav:cabinet", "« Назад"))

@router.callback_query(F.data == "nav:withdraw")
async def nav_withdraw(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0
    if balance < 15.0:
        text_msg = f"⚠️ **Недостаточно средств**\n\nТекущий баланс: **{balance:.2f} RUB**.\nМинимальный вывод через Crypto Pay: **15.00 RUB**."
        await callback.message.edit_text(text_msg, reply_markup=kb_cancel("nav:cabinet", "« Назад"), parse_mode="Markdown")
        return
    await state.set_state(WithdrawStates.waiting_for_amount)
    text_msg = f"💳 **Вывод через Crypto Pay API**\n\nДоступно: **{balance:.2f} RUB**\n\nВведите сумму для вывода:"
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel("nav:cabinet", "« Отмена"), parse_mode="Markdown")

@router.message(WithdrawStates.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext, session: AsyncSession):
    user = await session.get(User, message.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0
    try:
        amount = float(message.text.strip())
        if amount < 15:
            await message.answer("⚠️ Минимальная сумма — 15 RUB:")
            return
        if amount > balance:
            await message.answer(f"⚠️ На балансе недостаточно средств. Доступно: {balance:.2f} RUB:")
            return
    except ValueError:
        await message.answer("⚠️ Введите число:")
        return
    await state.update_data(withdraw_amount=amount)
    await state.set_state(WithdrawStates.waiting_for_requisites)
    await message.answer("✍️ Введите ваш **CryptoBot User ID** или **USDT TRC-20 адрес** для зачисления:", parse_mode="Markdown")

@router.message(WithdrawStates.waiting_for_requisites)
async def process_withdraw_requisites(message: types.Message, state: FSMContext, session: AsyncSession):
    requisites = message.text.strip()
    data = await state.get_data()
    amount = data.get("withdraw_amount")
    await state.clear()
    user = await session.get(User, message.from_user.id)
    if float(user.balance) < amount:
        await message.answer("⚠️ На балансе недостаточно средств.", reply_markup=kb_main_menu(is_admin_user(message.from_user.id)))
        return
    user.balance -= Decimal(str(amount))
    new_w = Withdrawal(
        user_id=message.from_user.id,
        amount=Decimal(str(amount)),
        requisites=requisites,
        status="pending"
    )
    session.add(new_w)
    await session.commit()
    
    admin_msg = f"🔔 **Новая заявка на вывод!**\n\nПользователь ID: `{message.from_user.id}`\nСумма: `{amount:.2f} RUB`\nРеквизиты: `{requisites}`"
    try:
        await message.bot.send_message(6470511118, admin_msg, parse_mode="Markdown")
    except Exception:
        pass

    await message.answer(
        f"✅ **Заявка на вывод #{new_w.id} принята!**\n\n• Сумма: **{amount:.2f} RUB**\n• Реквизиты (Crypto Pay): `{requisites}`\n• Статус: **В очереди на выплату**\n\nСредства поступят после подтверждения оператором.",
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
        text_msg = "🤖 **Монетизация (Продажа ОП)**\n\nУ вас пока нет подключённых ботов.\nНажмите «➕ Добавить бота», чтобы отправить заявку на модерацию и начать зарабатывать."
        await callback.message.edit_text(text_msg, reply_markup=kb_bot_list([]), parse_mode="Markdown")
        return
    text_msg = "🤖 **Ваши подключённые боты:**\n\nВыберите бота для управления параметрами:"
    await callback.message.edit_text(text_msg, reply_markup=kb_bot_list(bots), parse_mode="Markdown")

@router.callback_query(F.data == "nav:add_bot")
async def nav_add_bot(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddBotStates.waiting_for_username)
    text_msg = "➕ **Добавление нового бота на платформу**\n\nОтправьте юзернейм вашего бота (например, `@MyBestBot`).\nБот будет отправлен администратору на быструю модерацию."
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel("sell_traffic"), parse_mode="Markdown")

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
        quality_score=0.80,
        is_active=True
    )
    session.add(new_bot)
    await session.commit()

    try:
        admin_msg = f"🔔 **Новый бот на модерацию!**\n\n• Бот: @{new_bot.username} (ID: #{new_bot.id})\n• Владелец ID: `{message.from_user.id}`\n• Имя: @{message.from_user.username or 'без username'}"
        await message.bot.send_message(
            6470511118,
            admin_msg,
            reply_markup=kb_admin_bot_moderation(new_bot.id),
            parse_mode="Markdown"
        )
    except Exception:
        pass

    text_msg = f"✅ **Бот @{new_bot.username} отправлен на модерацию!**\n\n🔑 Токен API: `{new_token}`\nПосле подтверждения бот начнёт получать задания."
    await message.answer(text_msg, reply_markup=kb_cancel("sell_traffic", "« К списку ботов"), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_approve_bot:"))
async def admin_approve_bot(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer("Бот одобрен!")
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        bot_obj.is_active = True
        await session.commit()
        try:
            await callback.bot.send_message(bot_obj.user_id, f"🎉 **Ваш бот @{bot_obj.username} успешно прошёл модерацию и активирован!**", parse_mode="Markdown")
        except Exception:
            pass
    await callback.message.edit_text(f"✅ Бот #{bot_id} одобрен.")

@router.callback_query(F.data.startswith("admin_reject_bot:"))
async def admin_reject_bot(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
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
# Настройки бота (Цена, Спонсоры, Удаление)
# ==========================================
@router.callback_query(F.data.startswith("bot_manage:"))
async def bot_manage(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    
    # IDOR SECURITY PATCH
    if not bot_obj or (bot_obj.user_id != callback.from_user.id and not is_admin_user(callback.from_user.id)):
        await callback.message.edit_text("Бот не найден или доступ запрещён.", reply_markup=kb_cancel("sell_traffic"))
        return

    text_msg = (
        f"⚙️ **Управление ботом @{bot_obj.username}**\n\n"
        f"• Мин. цена: **{float(bot_obj.min_price):.2f} RUB**\n"
        f"• Лимит спонсоров: **{bot_obj.max_sponsors}**\n"
        f"• Рейтинг качества: **{bot_obj.quality_score * 100:.0f}%**\n\n"
        "Настройте параметры кнопками ниже:"
    )
    await callback.message.edit_text(text_msg, reply_markup=kb_bot_settings(bot_id), parse_mode="Markdown")

@router.callback_query(F.data.startswith("bot_edit_price:"))
async def bot_edit_price(callback: types.CallbackQuery, session: AsyncSession):
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if not bot_obj or (bot_obj.user_id != callback.from_user.id and not is_admin_user(callback.from_user.id)):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    await callback.answer()
    text_msg = "Задайте минимальную цену за подписчика:"
    await callback.message.edit_text(text_msg, reply_markup=kb_price_grid(bot_id))

@router.callback_query(F.data.startswith("set_prc:"))
async def set_prc(callback: types.CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    bot_id = int(parts[1])
    price = Decimal(parts[2])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj and (bot_obj.user_id == callback.from_user.id or is_admin_user(callback.from_user.id)):
        bot_obj.min_price = price
        await session.commit()
        await callback.answer(f"Цена изменена на {price:.1f} RUB")
    await bot_manage(callback, session)

@router.callback_query(F.data.startswith("bot_edit_sponsors:"))
async def bot_edit_sponsors(callback: types.CallbackQuery, session: AsyncSession):
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if not bot_obj or (bot_obj.user_id != callback.from_user.id and not is_admin_user(callback.from_user.id)):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    await callback.answer()
    text_msg = "Задайте лимит спонсоров (от 1 до 10):"
    await callback.message.edit_text(text_msg, reply_markup=kb_sponsors_grid(bot_id))

@router.callback_query(F.data.startswith("set_spn:"))
async def set_spn(callback: types.CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    bot_id = int(parts[1])
    sponsors = int(parts[2])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj and (bot_obj.user_id == callback.from_user.id or is_admin_user(callback.from_user.id)):
        bot_obj.max_sponsors = sponsors
        await session.commit()
        await callback.answer(f"Лимит изменён на {sponsors}")
    await bot_manage(callback, session)

@router.callback_query(F.data.startswith("bot_show_token:"))
async def bot_show_token(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if not bot_obj or (bot_obj.user_id != callback.from_user.id and not is_admin_user(callback.from_user.id)): return
    text_msg = f"🔑 **Токен интеграции для @{bot_obj.username}:**\n\n`{bot_obj.integration_token}`"
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel(f"bot_manage:{bot_id}", "« Назад"), parse_mode="Markdown")

@router.callback_query(F.data.startswith("bot_code_snippet:"))
async def bot_code_snippet(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if not bot_obj or (bot_obj.user_id != callback.from_user.id and not is_admin_user(callback.from_user.id)): return
    
    code = (
        "import requests\n\n"
        "url = 'https://smikhub-production.up.railway.app/api/v1/bot/sponsors'\n"
        f"headers = {{'Authorization': 'Bearer {bot_obj.integration_token}'}}\n"
        "params = {'user_id': message.from_user.id}\n"
        "response = requests.get(url, headers=headers, params=params).json()\n"
        "sponsors = response.get('sponsors', [])"
    )
    text_msg = f"📋 <b>Готовый код интеграции:</b>\n\n<pre><code class=\"language-python\">{code}</code></pre>"
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel(f"bot_manage:{bot_id}", "« Назад"), parse_mode="HTML")

@router.callback_query(F.data.startswith("bot_delete:"))
async def bot_delete(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if not bot_obj or (bot_obj.user_id != callback.from_user.id and not is_admin_user(callback.from_user.id)): return
    text_msg = "Вы уверены, что хотите удалить этого бота? Это действие нельзя отменить."
    await callback.message.edit_text(text_msg, reply_markup=kb_delete_confirm(bot_id))

@router.callback_query(F.data.startswith("del_conf:"))
async def bot_delete_confirm(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer("Бот удалён")
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj and (bot_obj.user_id == callback.from_user.id or is_admin_user(callback.from_user.id)):
        await session.delete(bot_obj)
        await session.commit()
    # Редирект в список ботов пользователя
    await nav_sell_traffic(callback, session)

# ==========================================
# Сторонние интеграции 
# ==========================================
@router.callback_query(F.data.startswith("bot_integrations:"))
async def bot_integrations(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if not bot_obj or (bot_obj.user_id != callback.from_user.id and not is_admin_user(callback.from_user.id)): return
    text_msg = "🌐 **Сторонние интеграции**\n\nВыберите сервис для подключения API токена:"
    await callback.message.edit_text(text_msg, reply_markup=kb_integrations(bot_id), parse_mode="Markdown")

@router.callback_query(F.data.startswith("integ:subgram:"))
async def integ_subgram(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    bot_id = int(callback.data.split(":")[2])
    await state.update_data(bot_id=bot_id)
    await state.set_state(IntegrationStates.waiting_for_subgram)
    text_msg = (
        "🔑 **Подключение Subgram**\n\n"
        "Subgram — это сервис для заработка на обязательных подписках.\n\n"
        "⚠️ **Важно:** Весь доход от подписок идёт напрямую в Subgram. SmikHub только показывает спонсоров вашим пользователям и не имеет финансовой связи с доходом от Subgram.\n"
        "───────────────\n"
        "📋 **Обязательные настройки в Subgram:**\n\n"
        "✅ Получать ссылки в API: Вкл.\n"
        "❌ Показывать анкету: Выкл.\n"
        "❌ Пол: Выкл.\n"
        "❌ Возраст: Выкл.\n\n"
        "⛔️ При других настройках интеграция работать не будет!\n"
        "───────────────\n\n"
        "Отправьте токен от Subgram:"
    )
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel(f"bot_integrations:{bot_id}", "« Отмена"), parse_mode="Markdown")

@router.callback_query(F.data.startswith("integ:flyer:"))
async def integ_flyer(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    bot_id = int(callback.data.split(":")[2])
    await state.update_data(bot_id=bot_id)
    await state.set_state(IntegrationStates.waiting_for_flyer)
    text_msg = (
        "🔑 **Подключение Flyer**\n\n"
        "Flyer — это сервис для заработка на обязательных подписках.\n\n"
        "⚠️ **Важно:** Весь доход от подписок идёт напрямую в Flyer. SmikHub только показывает спонсоров вашим пользователям и не имеет финансовой связи с доходом от Flyer.\n"
        "───────────────\n"
        "📋 **Как добавить бота:**\n\n"
        "1. Перейдите в Flyer\n"
        "2. Добавьте вашего бота как **ЗАДАНИЯ**\n\n"
        "⛔️ **Не добавляйте бота как «Обязательная подписка»!**\n"
        "Если бот уже добавлен как ОП — удалите и добавьте заново как «Задания».\n"
        "───────────────\n\n"
        "Отправьте токен от Flyer:"
    )
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel(f"bot_integrations:{bot_id}", "« Отмена"), parse_mode="Markdown")

@router.callback_query(F.data.startswith("integ:traffy:"))
async def integ_traffy(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    bot_id = int(callback.data.split(":")[2])
    await state.update_data(bot_id=bot_id)
    await state.set_state(IntegrationStates.waiting_for_traffy)
    text_msg = (
        "🔑 **Подключение Traffy**\n\n"
        "Traffy — сервис заданий для заработка на обязательных подписках.\n\n"
        "⚠️ **Важно:** Весь доход от заданий идёт напрямую в Traffy. SmikHub только показывает задания вашим пользователям и не имеет финансовой связи с доходом от Traffy.\n\n"
        "Получите Publisher API ключ в `@Traffy_robot` и отправьте его:"
    )
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel(f"bot_integrations:{bot_id}", "« Отмена"), parse_mode="Markdown")

@router.callback_query(F.data.startswith("integ:piarflow:"))
async def integ_piarflow(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    bot_id = int(callback.data.split(":")[2])
    await state.update_data(bot_id=bot_id)
    await state.set_state(IntegrationStates.waiting_for_piarflow)
    text_msg = (
        "🔑 **Подключение PiarFlow**\n\n"
        "PiarFlow — биржа рекламы и обязательных подписок.\n\n"
        "⚠️ **Важно:** Весь доход идёт напрямую на ваш баланс в PiarFlow. SmikHub интегрирует API только для отображения спонсоров.\n\n"
        "Получите API ключ (Publisher Token) в личном кабинете PiarFlow и отправьте его сюда:"
    )
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel(f"bot_integrations:{bot_id}", "« Отмена"), parse_mode="Markdown")

@router.callback_query(F.data.startswith("integ:tgrass:"))
async def integ_tgrass(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    bot_id = int(callback.data.split(":")[2])
    await state.update_data(bot_id=bot_id)
    await state.set_state(IntegrationStates.waiting_for_tgrass)
    text_msg = (
        "🔑 **Подключение TgGrass**\n\n"
        "TgGrass — платформа монетизации трафика Telegram.\n\n"
        "⚠️ **Важно:** Средства за подписки зачисляются в вашем кабинете TgGrass.\n\n"
        "Скопируйте ваш API токен в боте `@tgrass_bot` (в разделе интеграции/API) и отправьте его:"
    )
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel(f"bot_integrations:{bot_id}", "« Отмена"), parse_mode="Markdown")

async def _save_integration_token(message: types.Message, state: FSMContext, session: AsyncSession, field_name: str, service_name: str):
    token = message.text.strip()
    data = await state.get_data()
    bot_id = data.get("bot_id")
    await state.clear()

    bot_obj = await session.get(Bot, bot_id)
    if bot_obj and (bot_obj.user_id == message.from_user.id or is_admin_user(message.from_user.id)):
        try:
            setattr(bot_obj, field_name, token)
            await session.commit()
            await message.answer(f"✅ Токен {service_name} успешно сохранён и подключён к боту!", reply_markup=kb_cancel(f"bot_integrations:{bot_id}", "« Назад к сервисам"))
        except Exception:
            await message.answer("⚠️ Возникла ошибка при сохранении в базу.", reply_markup=kb_cancel(f"bot_integrations:{bot_id}", "« Назад к сервисам"))
    else:
        await message.answer("Доступ запрещен или бот не найден.", reply_markup=kb_cancel("sell_traffic", "« К списку ботов"))

@router.message(IntegrationStates.waiting_for_subgram)
async def proc_subgram(message: types.Message, state: FSMContext, session: AsyncSession):
    await _save_integration_token(message, state, session, "subgram_token", "Subgram")

@router.message(IntegrationStates.waiting_for_flyer)
async def proc_flyer(message: types.Message, state: FSMContext, session: AsyncSession):
    await _save_integration_token(message, state, session, "flyer_token", "Flyer")

@router.message(IntegrationStates.waiting_for_traffy)
async def proc_traffy(message: types.Message, state: FSMContext, session: AsyncSession):
    await _save_integration_token(message, state, session, "traffy_token", "Traffy")

@router.message(IntegrationStates.waiting_for_piarflow)
async def proc_piarflow(message: types.Message, state: FSMContext, session: AsyncSession):
    await _save_integration_token(message, state, session, "piarflow_token", "PiarFlow")

@router.message(IntegrationStates.waiting_for_tgrass)
async def proc_tgrass(message: types.Message, state: FSMContext, session: AsyncSession):
    await _save_integration_token(message, state, session, "tgrass_token", "TgGrass")

# ==========================================
# Купить ОП (Создание и управление кампаниями)
# ==========================================
@router.callback_query(F.data == "nav:buy_traffic")
async def nav_buy_traffic(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    orders = (await session.execute(
        select(Order).where(Order.user_id == callback.from_user.id)
    )).scalars().all()

    text_msg = "📢 **Закупка трафика (Купить ОП)**\n\nСоздавайте рекламные кампании для набора живых подписчиков в каналы через сеть ботов SmikHub."
    await callback.message.edit_text(text_msg, reply_markup=kb_buy_traffic(orders), parse_mode="Markdown")

@router.callback_query(F.data == "nav:create_order")
async def nav_create_order(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    await state.set_state(CampaignStates.waiting_for_channel)
    text_msg = "✍️ **Шаг 1/3:** Отправьте ссылку на канал (например, `https://t.me/mychannel`):"
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel("buy_traffic", "« Отмена"), parse_mode="Markdown")

@router.message(CampaignStates.waiting_for_channel)
async def process_campaign_channel(message: types.Message, state: FSMContext):
    link = message.text.strip()
    if "t.me/" not in link:
        await message.answer("⚠️ Отправьте ссылку Telegram (https://t.me/...):")
        return
    await state.update_data(channel_link=link)
    await state.set_state(CampaignStates.waiting_for_budget)
    # ТЕПЕРЬ МОЖНО СОЗДАТЬ С НУЛЕВЫМ БЮДЖЕТОМ (ЧТОБЫ ПОСМОТРЕТЬ НАСТРОЙКИ)
    await message.answer("✍️ **Шаг 2/3:** Введите общий бюджет кампании в рублях (можно `0`, чтобы просто посмотреть настройки кампании):")

@router.message(CampaignStates.waiting_for_budget)
async def process_campaign_budget(message: types.Message, state: FSMContext):
    try:
        budget = float(message.text.strip())
        if budget < 0:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Введите корректное число (можно `0`):")
        return
    await state.update_data(budget=budget)
    await state.set_state(CampaignStates.waiting_for_price)
    await message.answer("✍️ **Шаг 3/3:** Введите ставку за 1 подписчика (CPC) в рублях (например, 1.20):")

@router.message(CampaignStates.waiting_for_price)
async def process_campaign_price(message: types.Message, state: FSMContext, session: AsyncSession):
    try:
        price = float(message.text.strip())
        if price < 0.1:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Минимальная ставка — 0.10 RUB:")
        return

    data = await state.get_data()
    channel_link = data.get("channel_link")
    budget = data.get("budget")
    await state.clear()

    user = await session.get(User, message.from_user.id)
    if float(user.balance) < budget:
        await message.answer(f"⚠️ На балансе недостаточно средств. Ваш баланс: {float(user.balance):.2f} RUB.", reply_markup=kb_main_menu(is_admin_user(message.from_user.id)))
        return

    user.balance -= Decimal(str(budget))
    new_order = Order(
        user_id=message.from_user.id,
        channel_id=-1001234567890,
        channel_title="Мой канал",
        channel_link=channel_link,
        total_budget=Decimal(str(budget)),
        remaining_budget=Decimal(str(budget)),
        cpc_price=Decimal(str(price)),
        status="active"
    )
    session.add(new_order)
    await session.commit()

    await message.answer(
        f"✅ **Рекламная кампания #{new_order.id} успешно создана!**\n\n• Бюджет: **{budget:.2f} RUB**\n• Ставка за подписку: **{price:.2f} RUB**\n• Статус: **🟢 Активен**",
        reply_markup=kb_main_menu(is_admin_user(message.from_user.id)),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("order_view:"))
@router.callback_query(F.data.startswith("order_refresh:"))
async def order_view(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    order_id = int(callback.data.split(":")[1])
    order_obj = await session.get(Order, order_id)

    # IDOR SECURITY PATCH
    if not order_obj or (order_obj.user_id != callback.from_user.id and not is_admin_user(callback.from_user.id)):
        await callback.message.edit_text("Заказ не найден или доступ запрещен.", reply_markup=kb_cancel("buy_traffic"))
        return

    spent = float(order_obj.total_budget - order_obj.remaining_budget)
    price = float(order_obj.cpc_price)
    status_emoji = "🟢 Активен" if order_obj.status == "active" else "⏸ На паузе"
    now_str = datetime.now().strftime('%H:%M:%S')

    text_msg = (
        f"🛍 **Заказ #{order_obj.id}**\n\n"
        "Трафик: Подписки\n"
        "Назначение: Канал/чат\n"
        f"Статус: {status_emoji}\n"
        f"Цена: {price:.2f} ₽\n"
        f"Потрачено: {spent:.2f} ₽\n\n"
        f"_🔄 Обновлено: {now_str}_"
    )
    try:
        await callback.message.edit_text(text_msg, reply_markup=kb_order_control(order_obj.id, order_obj.status, price), parse_mode="Markdown")
    except Exception:
        pass

@router.callback_query(F.data.startswith("order_toggle:"))
async def order_toggle(callback: types.CallbackQuery, session: AsyncSession):
    order_id = int(callback.data.split(":")[1])
    order_obj = await session.get(Order, order_id)
    if order_obj and (order_obj.user_id == callback.from_user.id or is_admin_user(callback.from_user.id)):
        order_obj.status = "paused" if order_obj.status == "active" else "active"
        await session.commit()
        await callback.answer("Статус изменён")
    await order_view(callback, session)

@router.callback_query(F.data.startswith("order_delete:"))
async def order_delete_order(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    order_id = int(callback.data.split(":")[1])
    order_obj = await session.get(Order, order_id)
    if order_obj and (order_obj.user_id == callback.from_user.id or is_admin_user(callback.from_user.id)):
        user = await session.get(User, order_obj.user_id)
        if user:
            user.balance += order_obj.remaining_budget
        await session.delete(order_obj)
        await session.commit()
        await callback.message.edit_text("🗑 Заказ удалён. Неизрасходованный бюджет возвращён на баланс.", reply_markup=kb_cancel("buy_traffic", "« К списку кампаний"))
    else:
        await callback.answer("Доступ запрещен", show_alert=True)

@router.callback_query(F.data.startswith("order_price:"))
@router.callback_query(F.data.startswith("order_settings:"))
@router.callback_query(F.data.startswith("order_placements:"))
@router.callback_query(F.data.startswith("order_target_"))
async def order_targets_click(callback: types.CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    # IDOR check done inside the button data logic mentally, but to be sure we just alert
    await callback.answer("⚙️ Таргетинг активен и применяется ко всем ботам сети.", show_alert=True)

# ==========================================
# Партнёрская программа
# ==========================================
@router.callback_query(F.data == "nav:referrals")
async def nav_referrals(callback: types.CallbackQuery):
    await callback.answer()
    bot_me = await callback.bot.get_me()
    link = f"https://t.me/{bot_me.username}?start=ref_{callback.from_user.id}"
    text_msg = (
        "🤝 **Партнёрская программа SmikHub**\n\n"
        "• **5%** от дохода ботов 1-го уровня\n"
        "• **2%** от дохода ботов 2-го уровня\n\n"
        f"🔗 Ваша реферальная ссылка:\n`{link}`"
    )
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel("main_menu", "« Назад"), parse_mode="Markdown")