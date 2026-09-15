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
from smikhub.config import CRYPTO_BOT_TOKEN
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
    waiting_for_promo_code = State()

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

class SupportStates(StatesGroup):
    waiting_for_message = State()

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_bot_search = State()
    waiting_for_quality_score = State()
    waiting_for_user_search = State()
    waiting_for_user_balance = State()
    waiting_for_reserve_data = State()
    waiting_for_new_promo = State()
    waiting_for_reply = State()
    waiting_for_sys_value = State()

# ==========================================
# Вспомогательные функции
# ==========================================
async def get_sys_setting(session: AsyncSession, key: str, default: float) -> float:
    try:
        val = (await session.execute(text("SELECT value FROM system_settings WHERE key=:k"), {"k": key})).scalar()
        return float(val) if val else default
    except Exception:
        return default

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
# Клавиатуры пользователя
# ==========================================
def kb_main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="👤 Кабинет", callback_data="nav:cabinet")],
        [
            InlineKeyboardButton(text="🤖 Продать ОП", callback_data="nav:sell_traffic"),
            InlineKeyboardButton(text="📢 Купить ОП", callback_data="nav:buy_traffic"),
        ],
        [
            InlineKeyboardButton(text="🤝 Партнёрка", callback_data="nav:referrals"),
            InlineKeyboardButton(text="💬 Поддержка", callback_data="nav:support")
        ]
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="nav:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_cabinet() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Пополнить", callback_data="nav:topup"),
            InlineKeyboardButton(text="📤 Вывести", callback_data="nav:withdraw")
        ],
        [InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="nav:promo")],
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
            InlineKeyboardButton(text="🤖 Боты", callback_data="admin:bots_list"),
            InlineKeyboardButton(text="🔍 Поиск бота", callback_data="admin:search_bot")
        ],
        [
            InlineKeyboardButton(text="👤 Юзеры", callback_data="admin:users_search"),
            InlineKeyboardButton(text="📊 Финансы", callback_data="admin:finances")
        ],
        [
            InlineKeyboardButton(text="📤 Выводы", callback_data="admin:withdrawals"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")
        ],
        [
            InlineKeyboardButton(text="💰 Выдать баланс", callback_data="admin:topup_reserve"),
            InlineKeyboardButton(text="🎁 Промокоды", callback_data="admin:promo_manage")
        ],
        [
            InlineKeyboardButton(text="🛑 Модерация заказов", callback_data="admin:orders_list"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin:settings")
        ],
        [
            InlineKeyboardButton(text="💬 Поддержка (Тикеты)", callback_data="admin:support_list")
        ],
        [InlineKeyboardButton(text="« Назад в главное меню", callback_data="nav:main_menu")]
    ])

def kb_admin_user_card(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Изменить баланс", callback_data=f"admin:edit_user_bal:{user_id}")],
        [InlineKeyboardButton(text="🚫 Заблокировать юзера", callback_data=f"admin:ban_user:{user_id}")],
        [InlineKeyboardButton(text="« Назад в админку", callback_data="nav:admin")]
    ])

def kb_admin_bot_card(bot_id: int, is_active: bool) -> InlineKeyboardMarkup:
    ban_btn_text = "🔴 Заблокировать бота" if is_active else "🟢 Разблокировать бота"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ban_btn_text, callback_data=f"admin:toggle_bot:{bot_id}")],
        [InlineKeyboardButton(text="⭐ Изменить качество аудитории", callback_data=f"admin:edit_quality:{bot_id}")],
        [InlineKeyboardButton(text="🗑 Удалить бота из базы", callback_data=f"admin:delete_bot:{bot_id}")],
        [InlineKeyboardButton(text="« К списку ботов", callback_data="admin:bots_list")]
    ])

def kb_admin_order_card(order_id: int, status: str) -> InlineKeyboardMarkup:
    toggle_text = "⏸ Заморозить кампанию" if status == "active" else "▶️ Разморозить кампанию"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"admin:order_toggle:{order_id}")],
        [InlineKeyboardButton(text="🗑 Удалить и вернуть средства", callback_data=f"admin:order_delete:{order_id}")],
        [InlineKeyboardButton(text="« К списку заказов", callback_data="admin:orders_list")]
    ])

# ==========================================
# Главное меню и /start
# ==========================================
@router.message(CommandStart(deep_link=True))
@router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession, command: CommandObject = None):
    queries = [
        "ALTER TABLE bots ADD COLUMN subgram_token VARCHAR;",
        "ALTER TABLE bots ADD COLUMN flyer_token VARCHAR;",
        "ALTER TABLE bots ADD COLUMN traffy_token VARCHAR;",
        "ALTER TABLE bots ADD COLUMN piarflow_token VARCHAR;",
        "ALTER TABLE bots ADD COLUMN tgrass_token VARCHAR;",
        """CREATE TABLE IF NOT EXISTS promocodes (
            id SERIAL PRIMARY KEY, code VARCHAR(50) UNIQUE NOT NULL, amount NUMERIC(10, 2) NOT NULL, activations_left INTEGER NOT NULL
        );""",
        """CREATE TABLE IF NOT EXISTS promo_activations (
            id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL, promocode_id INTEGER NOT NULL, UNIQUE(user_id, promocode_id)
        );""",
        "CREATE TABLE IF NOT EXISTS system_settings (key VARCHAR(50) PRIMARY KEY, value VARCHAR(255));",
        """CREATE TABLE IF NOT EXISTS support_tickets (
            id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL, username VARCHAR(100), message TEXT NOT NULL, status VARCHAR(20) DEFAULT 'open', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );"""
    ]
    for q in queries:
        try:
            await session.execute(text(q))
            await session.commit()
        except Exception:
            await session.rollback()

    uid = message.from_user.id
    user = await session.get(User, uid)
    ref_id = None
    if command and command.args and command.args.startswith("ref_"):
        try:
            parsed = int(command.args.replace("ref_", ""))
            if parsed != uid: ref_id = parsed
        except ValueError: pass
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

@router.message(Command("fixdb"))
async def fix_db_command(message: types.Message, session: AsyncSession):
    if not is_admin_user(message.from_user.id): return
    queries = [
        "ALTER TABLE bots ADD COLUMN subgram_token VARCHAR;",
        "ALTER TABLE bots ADD COLUMN flyer_token VARCHAR;",
        "ALTER TABLE bots ADD COLUMN traffy_token VARCHAR;",
        "ALTER TABLE bots ADD COLUMN piarflow_token VARCHAR;",
        "ALTER TABLE bots ADD COLUMN tgrass_token VARCHAR;",
        "CREATE TABLE IF NOT EXISTS promocodes (id SERIAL PRIMARY KEY, code VARCHAR(50) UNIQUE NOT NULL, amount NUMERIC(10, 2) NOT NULL, activations_left INTEGER NOT NULL);",
        "CREATE TABLE IF NOT EXISTS promo_activations (id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL, promocode_id INTEGER NOT NULL, UNIQUE(user_id, promocode_id));",
        "CREATE TABLE IF NOT EXISTS system_settings (key VARCHAR(50) PRIMARY KEY, value VARCHAR(255));",
        "CREATE TABLE IF NOT EXISTS support_tickets (id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL, username VARCHAR(100), message TEXT NOT NULL, status VARCHAR(20) DEFAULT 'open', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
    ]
    for q in queries:
        try:
            await session.execute(text(q))
            await session.commit()
        except Exception:
            await session.rollback()
    await message.answer("✅ База данных полностью синхронизирована!")

# ==========================================
# 💬 ПОДДЕРЖКА (ТИКЕТЫ С USERNAME И КНОПКАМИ)
# ==========================================
@router.callback_query(F.data == "nav:support")
async def nav_support(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(SupportStates.waiting_for_message)
    await callback.message.edit_text(
        "💬 **Служба поддержки**\n\nОпишите вашу проблему или задайте вопрос в одном сообщении:", 
        reply_markup=kb_cancel("main_menu", "« Назад"), parse_mode="Markdown"
    )

@router.message(SupportStates.waiting_for_message)
async def support_msg_handler(message: types.Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    uid = message.from_user.id
    uname = message.from_user.username or "Без юзернейма"
    text_content = message.text or "[Медиа/Файл]"
    
    try:
        await session.execute(
            text("INSERT INTO support_tickets (user_id, username, message) VALUES (:uid, :uname, :msg)"),
            {"uid": uid, "uname": uname, "msg": text_content}
        )
        await session.commit()
    except Exception:
        await session.rollback()

    admin_id = 6470511118
    if getattr(config, 'ADMIN_CHAT_ID', None):
        admin_id = int(config.ADMIN_CHAT_ID)
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Ответить", callback_data=f"admin:reply:{uid}"),
            InlineKeyboardButton(text="👤 Профиль", callback_data=f"admin:user_lookup:{uid}")
        ],
        [
            InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"admin:ban_user:{uid}")
        ]
    ])
    
    ticket_text = (
        f"🆘 **Новое обращение в поддержку!**\n\n"
        f"👤 **От:** @{uname} (`{uid}`)\n"
        f"💬 **Сообщение:**\n{text_content}"
    )
    
    try:
        await message.bot.send_message(admin_id, ticket_text, reply_markup=kb, parse_mode="Markdown")
        await message.answer("✅ Ваше сообщение успешно отправлено в поддержку! Ожидайте ответа.", reply_markup=kb_main_menu(is_admin_user(uid)))
    except Exception as e:
        await message.answer(f"⚠️ Ошибка отправки: {e}")

@router.callback_query(F.data == "admin:support_list")
async def admin_support_list(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    
    tickets = (await session.execute(text("SELECT id, user_id, username, message, status FROM support_tickets WHERE status='open' ORDER BY id DESC LIMIT 15"))).mappings().all()
    
    if not tickets:
        await callback.message.edit_text("💬 **Тикеты поддержки**\n\nНет активных обращений.", reply_markup=kb_cancel("admin", "« Назад"), parse_mode="Markdown")
        return
        
    buttons = []
    for t in tickets:
        short_msg = t['message'][:20] + "..." if len(t['message']) > 20 else t['message']
        buttons.append([InlineKeyboardButton(text=f"@{t['username']}: {short_msg}", callback_data=f"admin:ticket_view:{t['id']}")])
    buttons.append([InlineKeyboardButton(text="« Назад в админку", callback_data="nav:admin")])
    
    await callback.message.edit_text("💬 **Активные тикеты поддержки:**\n\nНажмите на обращение для ответа:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin:ticket_view:"))
async def admin_ticket_view(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    t_id = int(callback.data.split(":")[3])
    t = (await session.execute(text("SELECT id, user_id, username, message FROM support_tickets WHERE id=:id"), {"id": t_id})).mappings().first()
    
    if not t:
        await callback.message.edit_text("Тикет не найден.", reply_markup=kb_cancel("admin:support_list"))
        return
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Ответить", callback_data=f"admin:reply:{t['user_id']}"),
            InlineKeyboardButton(text="✅ Закрыть тикет", callback_data=f"admin:close_ticket:{t['id']}")
        ],
        [InlineKeyboardButton(text="« К списку тикетов", callback_data="admin:support_list")]
    ])
    
    await callback.message.edit_text(
        f"🆘 **Тикет #{t['id']}**\n\n👤 **От:** @{t['username']} (`{t['user_id']}`)\n💬 **Текст:**\n{t['message']}",
        reply_markup=kb, parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("admin:close_ticket:"))
async def admin_close_ticket(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    t_id = int(callback.data.split(":")[3])
    await session.execute(text("UPDATE support_tickets SET status='closed' WHERE id=:id"), {"id": t_id})
    await session.commit()
    await callback.answer("Тикет закрыт!")
    await admin_support_list(callback, session)

@router.callback_query(F.data.startswith("admin:reply:"))
async def admin_reply_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user.id): return
    uid = int(callback.data.split(":")[2])
    await state.update_data(reply_to_user=uid)
    await state.set_state(AdminStates.waiting_for_reply)
    await callback.message.answer(f"✍️ Напишите текст ответа пользователю `{uid}`:", reply_markup=kb_cancel("admin"))
    await callback.answer()

@router.message(AdminStates.waiting_for_reply)
async def admin_send_reply(message: types.Message, state: FSMContext):
    if not is_admin_user(message.from_user.id): return
    data = await state.get_data()
    uid = data.get("reply_to_user")
    await state.clear()
    try:
        await message.bot.send_message(uid, "📩 **Ответ от администрации SmikHub:**", parse_mode="Markdown")
        await message.copy_to(uid)
        await message.answer(f"✅ Ответ успешно доставлен пользователю `{uid}`!", reply_markup=kb_cancel("admin", "« В админку"))
    except Exception:
        await message.answer("⚠️ Не удалось отправить сообщение.", reply_markup=kb_cancel("admin", "« В админку"))

@router.callback_query(F.data.startswith("admin:ban_user:"))
async def admin_ban_user(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    uid = int(callback.data.split(":")[3])
    u = await session.get(User, uid)
    if u:
        u.balance = Decimal("0.0")
        await session.commit()
    await callback.answer(f"🚫 Пользователь `{uid}` заблокирован (баланс обнулен).", show_alert=True)

@router.callback_query(F.data.startswith("admin:user_lookup:"))
async def admin_user_lookup(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    uid = int(callback.data.split(":")[3])
    u = await session.get(User, uid)
    if not u:
        await callback.answer("Юзер не найден", show_alert=True)
        return
    await callback.message.answer(f"👤 **Юзер ID:** `{u.id}`\n👤 **Username:** @{u.username}\n💰 **Баланс:** `{u.balance} RUB`", reply_markup=kb_admin_user_card(u.id), parse_mode="Markdown")
    await callback.answer()

# ==========================================
# ⚙️ СИСТЕМНЫЕ НАСТРОЙКИ
# ==========================================
@router.callback_query(F.data == "admin:settings")
async def admin_settings_menu(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    topup_val = await get_sys_setting(session, 'min_topup', 15.0)
    wd_val = await get_sys_setting(session, 'min_withdraw', 15.0)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Мин. пополнение ({topup_val} RUB)", callback_data="admin:set_sys:min_topup")],
        [InlineKeyboardButton(text=f"📤 Мин. вывод ({wd_val} RUB)", callback_data="admin:set_sys:min_withdraw")],
        [InlineKeyboardButton(text="« Назад в админку", callback_data="nav:admin")]
    ])
    await callback.message.edit_text("⚙️ **Системные настройки**\n\nИзменяйте лимиты платформы в один клик:", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin:set_sys:"))
async def admin_set_sys(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user.id): return
    key = callback.data.split(":")[2]
    await state.update_data(sys_key=key)
    await state.set_state(AdminStates.waiting_for_sys_value)
    name = "Мин. пополнение" if key == "min_topup" else "Мин. вывод"
    await callback.message.edit_text(f"⚙️ Введите новое значение для **{name}** (в рублях):", reply_markup=kb_cancel("admin:settings", "« Отмена"))
    await callback.answer()
    
@router.message(AdminStates.waiting_for_sys_value)
async def process_sys_value(message: types.Message, state: FSMContext, session: AsyncSession):
    if not is_admin_user(message.from_user.id): return
    data = await state.get_data()
    key = data.get("sys_key")
    try: val = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("⚠️ Введите число:")
        return
    try:
        await session.execute(text("INSERT INTO system_settings (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value=:v"), {"v": str(val), "k": key})
        await session.commit()
        await message.answer(f"✅ Настройка успешно обновлена!", reply_markup=kb_cancel("admin:settings", "« К настройкам"))
    except Exception:
        await session.rollback()
        await message.answer("⚠️ Ошибка сохранения в БД.", reply_markup=kb_cancel("admin:settings", "« Назад"))
    await state.clear()

# ==========================================
# Административная панель (Основное)
# ==========================================
@router.message(Command("admin"))
async def admin_command(message: types.Message, session: AsyncSession):
    if not is_admin_user(message.from_user.id): return
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
    if not is_admin_user(callback.from_user.id): return
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

@router.callback_query(F.data == "admin:promo_manage")
async def admin_promo_manage(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    promos = (await session.execute(text("SELECT code, amount, activations_left FROM promocodes WHERE activations_left > 0 ORDER BY id DESC LIMIT 10"))).mappings().all()
    promo_text = "🎁 **Управление промокодами**\n\n**Активные промокоды:**\n"
    if promos:
        for p in promos: promo_text += f"• `{p['code']}` — {p['amount']} RUB (Осталось: {p['activations_left']})\n"
    else: promo_text += "_Нет активных промокодов_\n"
    promo_text += "\nЧтобы создать промокод, отправьте:\n`КОД СУММА АКТИВАЦИИ`\nПример: `START50 50.0 100`"
    await state.set_state(AdminStates.waiting_for_new_promo)
    await callback.message.edit_text(promo_text, reply_markup=kb_cancel("admin", "« Назад"), parse_mode="Markdown")

@router.message(AdminStates.waiting_for_new_promo)
async def process_new_promo(message: types.Message, state: FSMContext, session: AsyncSession):
    if not is_admin_user(message.from_user.id): return
    parts = message.text.strip().split()
    if len(parts) != 3:
        await message.answer("⚠️ Неверный формат. Нужно: `КОД СУММА АКТИВАЦИИ`", parse_mode="Markdown")
        return
    code = parts[0].upper()
    try: amount = float(parts[1]); activations = int(parts[2])
    except ValueError:
        await message.answer("⚠️ Сумма и количество должны быть числами.")
        return
    try:
        await session.execute(text("INSERT INTO promocodes (code, amount, activations_left) VALUES (:code, :amount, :acts)"), {"code": code, "amount": amount, "acts": activations})
        await session.commit()
        await message.answer(f"✅ Промокод `{code}` на **{amount} RUB** успешно создан!", reply_markup=kb_cancel("admin", "« В админку"), parse_mode="Markdown")
    except Exception:
        await session.rollback()
        await message.answer(f"⚠️ Ошибка (возможно такой код уже существует).", reply_markup=kb_cancel("admin", "« В админку"))
    await state.clear()

@router.callback_query(F.data == "admin:orders_list")
async def admin_orders_list(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    orders = (await session.execute(select(Order).order_by(Order.id.desc()).limit(20))).scalars().all()
    if not orders:
        await callback.message.edit_text("📢 **Модерация заказов**\n\nНет активных заказов.", reply_markup=kb_cancel("admin", "« Назад"), parse_mode="Markdown")
        return
    buttons = []
    for o in orders:
        st = "🟢" if o.status == "active" else "⏸"
        short_link = o.link[:25] + "..." if len(o.link) > 25 else o.link
        buttons.append([InlineKeyboardButton(text=f"{st} Заказ #{o.id} | {short_link}", callback_data=f"admin:order_view:{o.id}")])
    buttons.append([InlineKeyboardButton(text="« Назад в админку", callback_data="nav:admin")])
    await callback.message.edit_text("🛑 **Модерация заказов**\n\nВыберите заказ для управления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin:order_view:"))
async def admin_order_view(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    order_id = int(callback.data.split(":")[2])
    order_obj = await session.get(Order, order_id)
    if not order_obj:
        await callback.message.edit_text("Заказ не найден.", reply_markup=kb_cancel("admin:orders_list"))
        return
    spent = float(order_obj.total_budget - order_obj.remaining_budget)
    st = "🟢 Активен" if order_obj.status == "active" else "⏸ Остановлен"
    text_msg = (
        f"📢 **Заказ #{order_obj.id}**\n\n"
        f"• **Создатель ID:** `{order_obj.user_id}`\n"
        f"• **Ссылка:** {order_obj.link}\n"
        f"• **Статус:** {st}\n\n"
        f"💰 **Бюджет:** `{float(order_obj.total_budget):.2f} RUB`\n"
        f"📉 **Потрачено:** `{spent:.2f} RUB`\n"
        f"💸 **Остаток:** `{float(order_obj.remaining_budget):.2f} RUB`"
    )
    await callback.message.edit_text(text_msg, reply_markup=kb_admin_order_card(order_obj.id, order_obj.status), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin:order_toggle:"))
async def admin_order_toggle(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    order_id = int(callback.data.split(":")[2])
    order_obj = await session.get(Order, order_id)
    if order_obj:
        order_obj.status = "paused" if order_obj.status == "active" else "active"
        await session.commit()
        await callback.answer("Статус изменен")
        await admin_order_view(callback, session)

@router.callback_query(F.data.startswith("admin:order_delete:"))
async def admin_order_delete(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    order_id = int(callback.data.split(":")[2])
    order_obj = await session.get(Order, order_id)
    if order_obj:
        user = await session.get(User, order_obj.user_id)
        if user: user.balance += order_obj.remaining_budget
        await session.delete(order_obj)
        await session.commit()
        await callback.answer("Заказ удален, средства возвращены.")
        await admin_orders_list(callback, session)

@router.callback_query(F.data == "admin:finances")
async def admin_finances(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    total_balance = (await session.execute(select(func.sum(User.balance)))).scalar() or 0
    total_orders_budget = (await session.execute(select(func.sum(Order.remaining_budget)).where(Order.status == 'active'))).scalar() or 0
    total_withdrawals = (await session.execute(select(func.sum(Withdrawal.amount)).where(Withdrawal.status == 'pending'))).scalar() or 0
    text_msg = (
        "📊 **Финансовая статистика**\n\n"
        f"💰 **На балансах юзеров:** `{float(total_balance):.2f} RUB`\n"
        f"📢 **В активных заказах:** `{float(total_orders_budget):.2f} RUB`\n"
        f"📤 **Ожидает вывода:** `{float(total_withdrawals):.2f} RUB`\n\n"
        f"📈 **ИТОГО обязательств:** `{float(total_balance + total_orders_budget + total_withdrawals):.2f} RUB`"
    )
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel("admin", "« Назад"), parse_mode="Markdown")

@router.callback_query(F.data == "admin:users_search")
async def admin_users_search(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_user_search)
    await callback.message.edit_text("🔍 **Поиск пользователя**\n\nВведите **ID** или **@username**:", reply_markup=kb_cancel("admin", "« Отмена"), parse_mode="Markdown")

@router.message(AdminStates.waiting_for_user_search)
async def process_admin_user_search(message: types.Message, state: FSMContext, session: AsyncSession):
    if not is_admin_user(message.from_user.id): return
    query = message.text.strip().replace("@", "")
    await state.clear()
    target_user = None
    if query.isdigit(): target_user = await session.get(User, int(query))
    if not target_user: target_user = (await session.execute(select(User).where(User.username.ilike(query)))).scalar_one_or_none()
    if not target_user:
        await message.answer("❌ Пользователь не найден.", reply_markup=kb_cancel("admin", "« В админку"))
        return
    user_bots = (await session.execute(select(func.count(Bot.id)).where(Bot.user_id == target_user.id))).scalar() or 0
    user_orders = (await session.execute(select(func.count(Order.id)).where(Order.user_id == target_user.id))).scalar() or 0
    text_msg = (
        f"👤 **Профиль пользователя**\n\n"
        f"🆔 **ID:** `{target_user.id}`\n"
        f"👤 **Username:** @{target_user.username or 'Не указан'}\n"
        f"💰 **Баланс:** `{float(target_user.balance or 0):.2f} RUB`\n\n"
        f"🤖 **Ботов:** `{user_bots}` | 📢 **Заказов:** `{user_orders}`"
    )
    await message.answer(text_msg, reply_markup=kb_admin_user_card(target_user.id), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin:edit_user_bal:"))
async def admin_edit_user_bal(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    uid = int(callback.data.split(":")[2])
    await state.update_data(target_user_id=uid)
    await state.set_state(AdminStates.waiting_for_user_balance)
    await callback.message.edit_text(f"💰 **Изменение баланса пользователя `{uid}`**\n\nВведите новый баланс в рублях:", reply_markup=kb_cancel("admin", "« Отмена"), parse_mode="Markdown")

@router.message(AdminStates.waiting_for_user_balance)
async def process_admin_user_balance(message: types.Message, state: FSMContext, session: AsyncSession):
    if not is_admin_user(message.from_user.id): return
    try: new_bal = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("⚠️ Введите число:")
        return
    data = await state.get_data()
    uid = data.get("target_user_id")
    await state.clear()
    target_user = await session.get(User, uid)
    if target_user:
        target_user.balance = Decimal(str(new_bal))
        await session.commit()
        await message.answer(f"✅ Баланс пользователя `{uid}` изменён на **{new_bal:.2f} RUB**.", reply_markup=kb_cancel("admin", "« В админку"), parse_mode="Markdown")
    else: await message.answer("❌ Пользователь не найден.", reply_markup=kb_cancel("admin", "« В админку"))

@router.callback_query(F.data == "admin:topup_reserve")
async def admin_topup_reserve(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_reserve_data)
    await callback.message.edit_text("💰 **Выдача баланса**\n\nОтправьте `ID` и `Сумму` через пробел:\n`123456789 500`", reply_markup=kb_cancel("admin", "« Отмена"), parse_mode="Markdown")

@router.message(AdminStates.waiting_for_reserve_data)
async def process_admin_topup_reserve(message: types.Message, state: FSMContext, session: AsyncSession):
    if not is_admin_user(message.from_user.id): return
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("⚠️ Формат: `ID Сумма`", parse_mode="Markdown")
        return
    try: target_id = int(parts[0]); amount = float(parts[1])
    except ValueError:
        await message.answer("⚠️ Должны быть числа.")
        return
    target_user = await session.get(User, target_id)
    if not target_user:
        target_user = User(id=target_id, username=f"user_{target_id}")
        session.add(target_user)
    target_user.balance = (target_user.balance or Decimal("0.0")) + Decimal(str(amount))
    await session.commit()
    await state.clear()
    await message.answer(f"✅ Баланс `{target_id}` пополнен на **{amount:.2f} RUB**.", reply_markup=kb_cancel("admin", "« В админку"), parse_mode="Markdown")

@router.callback_query(F.data == "admin:bots_list")
async def admin_bots_list(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    bots = (await session.execute(select(Bot).order_by(Bot.id.desc()).limit(30))).scalars().all()
    buttons = []
    for b in bots:
        st = "🟢" if b.is_active else "🔴"
        q_pct = int((b.quality_score or 0.8) * 100)
        buttons.append([InlineKeyboardButton(text=f"{st} #{b.id} @{b.username} (Качество: {q_pct}%)", callback_data=f"admin:bot_card:{b.id}")])
    buttons.append([InlineKeyboardButton(text="🔍 Найти бота", callback_data="admin:search_bot")])
    buttons.append([InlineKeyboardButton(text="« Назад в админку", callback_data="nav:admin")])
    await callback.message.edit_text("🤖 **Боты сети:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "admin:search_bot")
async def admin_search_bot(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_bot_search)
    await callback.message.edit_text("🔍 Введите **ID** или **@username** бота:", reply_markup=kb_cancel("admin", "« Отмена"), parse_mode="Markdown")

@router.message(AdminStates.waiting_for_bot_search)
async def process_admin_bot_search(message: types.Message, state: FSMContext, session: AsyncSession):
    if not is_admin_user(message.from_user.id): return
    query = message.text.strip().replace("@", "")
    await state.clear()
    bot_obj = None
    if query.isdigit(): bot_obj = await session.get(Bot, int(query))
    if not bot_obj: bot_obj = (await session.execute(select(Bot).where(Bot.username.ilike(query)))).scalar_one_or_none()
    if not bot_obj:
        await message.answer("❌ Бот не найден.", reply_markup=kb_cancel("admin", "« В админку"))
        return
    await render_bot_admin_card(message, bot_obj, session)

@router.callback_query(F.data.startswith("admin:bot_card:"))
async def admin_bot_card_handler(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
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
    status_text = "🟢 Активен" if bot_obj.is_active else "🔴 Заблокирован"

    card_text = (
        f"📊 **Бот #{bot_obj.id} — @{bot_obj.username}**\n\n"
        f"• **Статус:** {status_text}\n"
        f"• **Владелец:** {owner_str}\n"
        f"• **Качество:** **{quality_pct}%**\n"
        f"• **Мин. CPC:** `{float(bot_obj.min_price):.2f} RUB`\n"
        f"• **Спонсоров:** `{bot_obj.max_sponsors}`"
    )
    kb = kb_admin_bot_card(bot_obj.id, bot_obj.is_active)
    if edit: await message_or_callback_msg.edit_text(card_text, reply_markup=kb, parse_mode="Markdown")
    else: await message_or_callback_msg.answer(card_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin:toggle_bot:"))
async def admin_toggle_bot(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    bot_id = int(callback.data.split(":")[2])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        bot_obj.is_active = not bot_obj.is_active
        await session.commit()
        await callback.answer("Статус изменен!")
        await render_bot_admin_card(callback.message, bot_obj, session, edit=True)

@router.callback_query(F.data.startswith("admin:edit_quality:"))
async def admin_edit_quality(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    bot_id = int(callback.data.split(":")[2])
    await state.update_data(target_bot_id=bot_id)
    await state.set_state(AdminStates.waiting_for_quality_score)
    await callback.message.edit_text(f"⭐ Введите качество от `0.1` до `1.0` для бота #{bot_id}:", reply_markup=kb_cancel("admin:bots_list", "« Отмена"), parse_mode="Markdown")

@router.message(AdminStates.waiting_for_quality_score)
async def process_admin_quality_score(message: types.Message, state: FSMContext, session: AsyncSession):
    if not is_admin_user(message.from_user.id): return
    try:
        val = float(message.text.strip().replace(",", "."))
        if val < 0.05 or val > 1.0: raise ValueError()
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
        await message.answer(f"✅ Качество бота #{bot_id} установлено на **{int(val * 100)}%**.")
        await render_bot_admin_card(message, bot_obj, session, edit=False)

@router.callback_query(F.data.startswith("admin:delete_bot:"))
async def admin_delete_bot(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    bot_id = int(callback.data.split(":")[2])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        await session.delete(bot_obj)
        await session.commit()
        await callback.answer("Бот удалён.")
    await admin_bots_list(callback, session)

@router.callback_query(F.data == "admin:withdrawals")
async def admin_withdrawals(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    items = (await session.execute(select(Withdrawal).where(Withdrawal.status == "pending").order_by(Withdrawal.id.desc()).limit(10))).scalars().all()
    if not items:
        await callback.message.edit_text("📤 **Выводы**\n\nНет заявок.", reply_markup=kb_cancel("admin", "« Назад"), parse_mode="Markdown")
        return
    buttons = []
    text_lines = ["📤 **Заявки на вывод:**\n"]
    for w in items:
        text_lines.append(f"• #{w.id}: `{float(w.amount):.2f} RUB` | `{w.requisites}`")
        buttons.append([InlineKeyboardButton(text=f"✅ #{w.id}", callback_data=f"admin_w_pay:{w.id}"), InlineKeyboardButton(text=f"❌ #{w.id}", callback_data=f"admin_w_rej:{w.id}")])
    buttons.append([InlineKeyboardButton(text="« Назад", callback_data="nav:admin")])
    await callback.message.edit_text("\n".join(text_lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_w_pay:"))
async def admin_w_pay(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    w_id = int(callback.data.split(":")[1])
    w_obj = await session.get(Withdrawal, w_id)
    if w_obj:
        w_obj.status = "completed"
        await session.commit()
        try: await callback.bot.send_message(w_obj.user_id, f"✅ Выплата #{w_obj.id} на сумму {w_obj.amount:.2f} RUB отправлена!")
        except Exception: pass
        await callback.answer("Выполнено.")
    await admin_withdrawals(callback, session)

@router.callback_query(F.data.startswith("admin_w_rej:"))
async def admin_w_rej(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    w_id = int(callback.data.split(":")[1])
    w_obj = await session.get(Withdrawal, w_id)
    if w_obj:
        w_obj.status = "rejected"
        user = await session.get(User, w_obj.user_id)
        if user: user.balance += w_obj.amount
        await session.commit()
        try: await callback.bot.send_message(w_obj.user_id, f"❌ Выплата #{w_obj.id} отклонена, средства возвращены.")
        except Exception: pass
        await callback.answer("Отклонено.")
    await admin_withdrawals(callback, session)

@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_prompt(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user.id): return
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.message.edit_text("📢 **Рассылка**\n\nОтправьте текст или медиа:", reply_markup=kb_cancel("admin", "« Отмена"), parse_mode="Markdown")

@router.message(AdminStates.waiting_for_broadcast)
async def process_admin_broadcast(message: types.Message, state: FSMContext, session: AsyncSession):
    if not is_admin_user(message.from_user.id): return
    await state.clear()
    users = (await session.execute(select(User.id))).scalars().all()
    sent_count = 0
    status_msg = await message.answer(f"⏳ Рассылка на {len(users)} чел...")
    for uid in users:
        try: await message.copy_to(chat_id=uid); sent_count += 1
        except Exception: continue
    await status_msg.edit_text(f"✅ Доставлено: {sent_count} из {len(users)}.", reply_markup=kb_cancel("admin", "« В админку"))

# ==========================================
# Кабинет пользователя (Пополнить / Промокод / Вывести)
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
        "Выберите действие:"
    )
    await callback.message.edit_text(text_msg, reply_markup=kb_cabinet(), parse_mode="Markdown")

@router.callback_query(F.data == "nav:topup")
async def nav_topup(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback.answer()
    await state.set_state(TopupStates.waiting_for_crypto_amount)
    min_t = await get_sys_setting(session, 'min_topup', 15.0)
    await callback.message.edit_text(f"🤖 **Пополнение**\n\nВведите сумму (минимум {min_t} RUB):", reply_markup=kb_cancel("nav:cabinet", "« Назад"), parse_mode="Markdown")

@router.message(TopupStates.waiting_for_crypto_amount)
async def process_crypto_amount(message: types.Message, state: FSMContext, session: AsyncSession):
    min_t = await get_sys_setting(session, 'min_topup', 15.0)
    try:
        amount = float(message.text.strip())
        if amount < min_t: raise ValueError()
    except ValueError:
        await message.answer(f"⚠️ Не менее {min_t} руб.:")
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
                    json={"asset": "USDT", "amount": str(usdt_amount), "description": f"Пополнение SmikHub: {amount} RUB", "payload": f"topup_{message.from_user.id}_{amount}"}
                )
                data = await res.json()
                if data.get("ok"): invoice_url = data["result"]["pay_url"]
        except Exception: pass
            
    if invoice_url:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Оплатить счет", url=invoice_url)], [InlineKeyboardButton(text="« Назад", callback_data="nav:cabinet")]])
        await message.answer(f"🧾 Счёт на **{amount:.2f} RUB** ({usdt_amount} USDT):", reply_markup=kb, parse_mode="Markdown")
    else:
        await message.answer("❌ Ошибка связи с CryptoBot.", reply_markup=kb_cancel("nav:cabinet", "« Назад"), parse_mode="Markdown")

@router.callback_query(F.data == "nav:promo")
async def nav_promo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TopupStates.waiting_for_promo_code)
    await callback.message.edit_text("🎁 **Промокод**\n\nВведите код:", reply_markup=kb_cancel("nav:cabinet", "« Отмена"), parse_mode="Markdown")

@router.message(TopupStates.waiting_for_promo_code)
async def process_promo_code(message: types.Message, state: FSMContext, session: AsyncSession):
    code = message.text.strip().upper()
    await state.clear()
    try:
        promo = (await session.execute(text("SELECT id, reward_amount as amount, max_activations - current_activations as activations_left FROM promo_codes WHERE code = :code"), {"code": code})).mappings().first()
        if not promo or promo['activations_left'] <= 0:
            await message.answer("❌ Промокод недействителен.", reply_markup=kb_cancel("nav:cabinet", "« В кабинет"))
            return
        activation = (await session.execute(text("SELECT id FROM promo_activations WHERE user_id = :uid AND promo_id = :pid"), {"uid": message.from_user.id, "pid": promo['id']})).mappings().first()
        if activation:
            await message.answer("⚠️ Вы уже активировали его.", reply_markup=kb_cancel("nav:cabinet", "« В кабинет"))
            return
        user = await session.get(User, message.from_user.id)
        if user:
            user.balance += Decimal(str(promo['amount']))
            await session.execute(text("UPDATE promo_codes SET current_activations = current_activations + 1 WHERE id = :pid"), {"pid": promo['id']})
            await session.execute(text("INSERT INTO promo_activations (user_id, promo_id) VALUES (:uid, :pid)"), {"uid": user.id, "pid": promo['id']})
            await session.commit()
            await message.answer(f"🎉 **Активировано!** Зачислено: **{promo['amount']} RUB**", reply_markup=kb_main_menu(is_admin_user(message.from_user.id)), parse_mode="Markdown")
    except Exception:
        await session.rollback()
        await message.answer("⚠️ Ошибка. Выполните /fixdb", reply_markup=kb_cancel("nav:cabinet", "« В кабинет"))

@router.callback_query(F.data == "nav:withdraw")
async def nav_withdraw(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    user = await session.get(User, callback.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0
    min_w = await get_sys_setting(session, 'min_withdraw', 15.0)
    if balance < min_w:
        await callback.message.edit_text(f"⚠️ **Недостаточно средств** (Мин: {min_w} RUB)", reply_markup=kb_cancel("nav:cabinet", "« Назад"), parse_mode="Markdown")
        return
    await state.set_state(WithdrawStates.waiting_for_amount)
    await callback.message.edit_text(f"💳 **Вывод**\n\nДоступно: **{balance:.2f} RUB**\nВведите сумму:", reply_markup=kb_cancel("nav:cabinet", "« Отмена"), parse_mode="Markdown")

@router.message(WithdrawStates.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext, session: AsyncSession):
    user = await session.get(User, message.from_user.id)
    balance = float(user.balance) if user and user.balance else 0.0
    min_w = await get_sys_setting(session, 'min_withdraw', 15.0)
    try:
        amount = float(message.text.strip())
        if amount < min_w or amount > balance: raise ValueError()
    except ValueError:
        await message.answer(f"⚠️ Неверная сумма (мин. {min_w}, доступно {balance:.2f}):")
        return
    await state.update_data(withdraw_amount=amount)
    await state.set_state(WithdrawStates.waiting_for_requisites)
    await message.answer("✍️ Введите **CryptoBot User ID** или **USDT TRC-20 адрес**:", parse_mode="Markdown")

@router.message(WithdrawStates.waiting_for_requisites)
async def process_withdraw_requisites(message: types.Message, state: FSMContext, session: AsyncSession):
    requisites = message.text.strip()
    data = await state.get_data()
    amount = data.get("withdraw_amount")
    await state.clear()
    user = await session.get(User, message.from_user.id)
    user.balance -= Decimal(str(amount))
    new_w = Withdrawal(user_id=message.from_user.id, amount=Decimal(str(amount)), requisites=requisites, status="pending")
    session.add(new_w)
    await session.commit()
    
    try: await message.bot.send_message(6470511118, f"🔔 **Новый вывод!**\nID: `{message.from_user.id}`\nСумма: `{amount:.2f} RUB`\nРеквизиты: `{requisites}`", parse_mode="Markdown")
    except Exception: pass

    await message.answer(f"✅ **Заявка #{new_w.id} создана!** Ожидайте выплаты.", reply_markup=kb_main_menu(is_admin_user(message.from_user.id)), parse_mode="Markdown")

# ==========================================
# Продать ОП (Добавление бота, Модерация)
# ==========================================
@router.callback_query(F.data == "nav:sell_traffic")
async def nav_sell_traffic(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bots = (await session.execute(select(Bot).where(Bot.user_id == callback.from_user.id))).scalars().all()
    if not bots:
        await callback.message.edit_text("🤖 **Монетизация**\n\nУ вас нет ботов. Нажмите «➕ Добавить бота»:", reply_markup=kb_bot_list([]), parse_mode="Markdown")
        return
    await callback.message.edit_text("🤖 **Ваши боты:**", reply_markup=kb_bot_list(bots), parse_mode="Markdown")

@router.callback_query(F.data == "nav:add_bot")
async def nav_add_bot(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddBotStates.waiting_for_username)
    await callback.message.edit_text("➕ Отправьте юзернейм вашего бота (например, `@MyBot`):", reply_markup=kb_cancel("sell_traffic"), parse_mode="Markdown")

@router.message(AddBotStates.waiting_for_username)
async def process_add_bot_username(message: types.Message, state: FSMContext, session: AsyncSession):
    raw_name = message.text.strip().replace("@", "")
    if len(raw_name) < 3:
        await message.answer("⚠️ Неверный юзернейм:")
        return
    await state.clear()
    new_token = secrets.token_hex(16)
    new_bot = Bot(user_id=message.from_user.id, username=raw_name, integration_token=new_token, min_price=Decimal("0.50"), max_sponsors=3, quality_score=0.80, is_active=True)
    session.add(new_bot)
    await session.commit()

    try: await message.bot.send_message(6470511118, f"🔔 **Новый бот:** @{new_bot.username} (ID: #{new_bot.id})", reply_markup=kb_admin_bot_moderation(new_bot.id), parse_mode="Markdown")
    except Exception: pass

    await message.answer(f"✅ **Бот @{new_bot.username} на модерации!**\n\n🔑 Токен: `{new_token}`", reply_markup=kb_cancel("sell_traffic", "« К списку"), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_approve_bot:"))
async def admin_approve_bot(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        bot_obj.is_active = True
        await session.commit()
        try: await callback.bot.send_message(bot_obj.user_id, f"🎉 Ваш бот @{bot_obj.username} одобрен!", parse_mode="Markdown")
        except Exception: pass
    await callback.message.edit_text(f"✅ Бот #{bot_id} одобрен.")

@router.callback_query(F.data.startswith("admin_reject_bot:"))
async def admin_reject_bot(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin_user(callback.from_user.id): return
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        try: await callback.bot.send_message(bot_obj.user_id, f"⚠️ Бот @{bot_obj.username} отклонён.", parse_mode="Markdown")
        except Exception: pass
        await session.delete(bot_obj)
        await session.commit()
    await callback.message.edit_text(f"❌ Бот #{bot_id} отклонён.")

# ==========================================
# Управление ботом
# ==========================================
@router.callback_query(F.data.startswith("bot_manage:"))
async def bot_manage(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if not bot_obj or (bot_obj.user_id != callback.from_user.id and not is_admin_user(callback.from_user.id)):
        await callback.message.edit_text("Бот не найден.", reply_markup=kb_cancel("sell_traffic"))
        return

    text_msg = (
        f"⚙️ **Управление @{bot_obj.username}**\n\n"
        f"• Мин. цена: **{float(bot_obj.min_price):.2f} RUB**\n"
        f"• Лимит: **{bot_obj.max_sponsors}**\n"
        f"• Качество: **{bot_obj.quality_score * 100:.0f}%**"
    )
    await callback.message.edit_text(text_msg, reply_markup=kb_bot_settings(bot_id), parse_mode="Markdown")

@router.callback_query(F.data.startswith("bot_edit_price:"))
async def bot_edit_price(callback: types.CallbackQuery, session: AsyncSession):
    bot_id = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.edit_text("Задайте мин. цену за подписчика:", reply_markup=kb_price_grid(bot_id))

@router.callback_query(F.data.startswith("set_prc:"))
async def set_prc(callback: types.CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    bot_id = int(parts[1])
    price = Decimal(parts[2])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        bot_obj.min_price = price
        await session.commit()
        await callback.answer(f"Цена: {price}р")
    await bot_manage(callback, session)

@router.callback_query(F.data.startswith("bot_edit_sponsors:"))
async def bot_edit_sponsors(callback: types.CallbackQuery, session: AsyncSession):
    bot_id = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.edit_text("Лимит спонсоров (1-10):", reply_markup=kb_sponsors_grid(bot_id))

@router.callback_query(F.data.startswith("set_spn:"))
async def set_spn(callback: types.CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    bot_id = int(parts[1])
    sponsors = int(parts[2])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        bot_obj.max_sponsors = sponsors
        await session.commit()
        await callback.answer(f"Лимит: {sponsors}")
    await bot_manage(callback, session)

@router.callback_query(F.data.startswith("bot_show_token:"))
async def bot_show_token(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    await callback.message.edit_text(f"🔑 **Токен:**\n\n`{bot_obj.integration_token}`", reply_markup=kb_cancel(f"bot_manage:{bot_id}", "« Назад"), parse_mode="Markdown")

@router.callback_query(F.data.startswith("bot_code_snippet:"))
async def bot_code_snippet(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if not bot_obj or (bot_obj.user_id != callback.from_user.id and not is_admin_user(callback.from_user.id)): return
    
    code = (
        "import requests\n\n"
        "base_url = 'https://smikhub-production.up.railway.app'\n"
        "url = f\"{base_url}/api/v1/bot/sponsors\"\n"
        f"headers = {{'Authorization': 'Bearer {bot_obj.integration_token}'}}\n"
        "params = {'user_id': message.from_user.id}\n"
        "response = requests.get(url, headers=headers, params=params).json()\n"
        "sponsors = response.get('sponsors', [])"
    )
    text_msg = f"📋 <b>Код интеграции:</b>\n\n<pre><code class=\"language-python\">{code}</code></pre>"
    await callback.message.edit_text(text_msg, reply_markup=kb_cancel(f"bot_manage:{bot_id}", "« Назад"), parse_mode="HTML")

@router.callback_query(F.data.startswith("bot_delete:"))
async def bot_delete(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    await callback.message.edit_text("Удалить бота?", reply_markup=kb_delete_confirm(bot_id))

@router.callback_query(F.data.startswith("del_conf:"))
async def bot_delete_confirm(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer("Удалено")
    bot_id = int(callback.data.split(":")[1])
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        await session.delete(bot_obj)
        await session.commit()
    await nav_sell_traffic(callback, session)

# ==========================================
# Интеграции
# ==========================================
@router.callback_query(F.data.startswith("bot_integrations:"))
async def bot_integrations(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    bot_id = int(callback.data.split(":")[1])
    await callback.message.edit_text("🌐 **Сторонние шлюзы:**", reply_markup=kb_integrations(bot_id), parse_mode="Markdown")

@router.callback_query(F.data.startswith("integ:"))
async def integ_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    service = parts[1]
    bot_id = int(parts[2])
    await state.update_data(bot_id=bot_id)
    
    states_map = {
        "subgram": IntegrationStates.waiting_for_subgram,
        "flyer": IntegrationStates.waiting_for_flyer,
        "traffy": IntegrationStates.waiting_for_traffy,
        "piarflow": IntegrationStates.waiting_for_piarflow,
        "tgrass": IntegrationStates.waiting_for_tgrass,
    }
    if service in states_map:
        await state.set_state(states_map[service])
    await callback.message.edit_text(f"🔑 Отправьте токен для **{service.upper()}**:", reply_markup=kb_cancel(f"bot_integrations:{bot_id}", "« Отмена"), parse_mode="Markdown")

async def _save_token(message: types.Message, state: FSMContext, session: AsyncSession, field: str, name: str):
    token = message.text.strip()
    data = await state.get_data()
    bot_id = data.get("bot_id")
    await state.clear()
    bot_obj = await session.get(Bot, bot_id)
    if bot_obj:
        setattr(bot_obj, field, token)
        await session.commit()
        await message.answer(f"✅ Токен {name} сохранен!", reply_markup=kb_cancel(f"bot_integrations:{bot_id}", "« Назад"))

@router.message(IntegrationStates.waiting_for_subgram)
async def p_sub(m: types.Message, s: FSMContext, db: AsyncSession): await _save_token(m, s, db, "subgram_token", "Subgram")
@router.message(IntegrationStates.waiting_for_flyer)
async def p_fly(m: types.Message, s: FSMContext, db: AsyncSession): await _save_token(m, s, db, "flyer_token", "Flyer")
@router.message(IntegrationStates.waiting_for_traffy)
async def p_trf(m: types.Message, s: FSMContext, db: AsyncSession): await _save_token(m, s, db, "traffy_token", "Traffy")
@router.message(IntegrationStates.waiting_for_piarflow)
async def p_prf(m: types.Message, s: FSMContext, db: AsyncSession): await _save_token(m, s, db, "piarflow_token", "PiarFlow")
@router.message(IntegrationStates.waiting_for_tgrass)
async def p_tgr(m: types.Message, s: FSMContext, db: AsyncSession): await _save_token(m, s, db, "tgrass_token", "TgGrass")

# ==========================================
# Купить ОП
# ==========================================
@router.callback_query(F.data == "nav:buy_traffic")
async def nav_buy_traffic(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    orders = (await session.execute(select(Order).where(Order.user_id == callback.from_user.id))).scalars().all()
    await callback.message.edit_text("📢 **Закупка трафика**", reply_markup=kb_buy_traffic(orders), parse_mode="Markdown")

@router.callback_query(F.data == "nav:create_order")
async def nav_create_order(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(CampaignStates.waiting_for_channel)
    await callback.message.edit_text("✍️ Отправьте ссылку на канал (`https://t.me/...`):", reply_markup=kb_cancel("buy_traffic", "« Отмена"), parse_mode="Markdown")

@router.message(CampaignStates.waiting_for_channel)
async def p_ch(message: types.Message, state: FSMContext):
    if "t.me/" not in message.text:
        await message.answer("⚠️ Нужна ссылка t.me:")
        return
    await state.update_data(channel_link=message.text.strip())
    await state.set_state(CampaignStates.waiting_for_budget)
    await message.answer("✍️ Введите бюджет в рублях (можно 0):")

@router.message(CampaignStates.waiting_for_budget)
async def p_bg(message: types.Message, state: FSMContext):
    try: b = float(message.text.strip()); assert b >= 0
    except:
        await message.answer("⚠️ Число не менее 0:")
        return
    await state.update_data(budget=b)
    await state.set_state(CampaignStates.waiting_for_price)
    await message.answer("✍️ Введите ставку CPC за 1 подписчика (например, 1.0):")

@router.message(CampaignStates.waiting_for_price)
async def p_pr(message: types.Message, state: FSMContext, session: AsyncSession):
    try: p = float(message.text.strip()); assert p >= 0.1
    except:
        await message.answer("⚠️ Ставка не менее 0.10:")
        return
    data = await state.get_data()
    await state.clear()
    
    user = await session.get(User, message.from_user.id)
    bud = data.get("budget")
    if float(user.balance) < bud:
        await message.answer("⚠️ Недостаточно средств на балансе.")
        return
        
    user.balance -= Decimal(str(bud))
    order = Order(user_id=message.from_user.id, channel_id=-1001, title="Канал", link=data.get("channel_link"), total_budget=Decimal(str(bud)), remaining_budget=Decimal(str(bud)), price_per_sub=Decimal(str(p)), status="active")
    session.add(order)
    await session.commit()
    await message.answer(f"✅ Кампания #{order.id} создана!", reply_markup=kb_main_menu(is_admin_user(message.from_user.id)))

@router.callback_query(F.data.startswith("order_view:"))
async def order_view(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer()
    oid = int(callback.data.split(":")[1])
    o = await session.get(Order, oid)
    if not o: return
    spent = float(o.total_budget - o.remaining_budget)
    await callback.message.edit_text(f"🛍 **Заказ #{o.id}**\nСтатус: {o.status}\nБюджет: {o.total_budget}р\nПотрачено: {spent:.2f}р", reply_markup=kb_order_control(o.id, o.status, float(o.price_per_sub)), parse_mode="Markdown")

@router.callback_query(F.data.startswith("order_toggle:"))
async def order_toggle(callback: types.CallbackQuery, session: AsyncSession):
    oid = int(callback.data.split(":")[1])
    o = await session.get(Order, oid)
    if o:
        o.status = "paused" if o.status == "active" else "active"
        await session.commit()
    await order_view(callback, session)

@router.callback_query(F.data.startswith("order_delete:"))
async def order_del(callback: types.CallbackQuery, session: AsyncSession):
    oid = int(callback.data.split(":")[1])
    o = await session.get(Order, oid)
    if o:
        u = await session.get(User, o.user_id)
        if u: u.balance += o.remaining_budget
        await session.delete(o)
        await session.commit()
    await callback.message.edit_text("🗑 Заказ удален, средства возвращены.", reply_markup=kb_cancel("buy_traffic"))

@router.callback_query(F.data == "nav:referrals")
async def nav_ref(callback: types.CallbackQuery):
    await callback.answer()
    m = await callback.bot.get_me()
    await callback.message.edit_text(f"🤝 **Реферальная ссылка:**\n\n`https://t.me/{m.username}?start=ref_{callback.from_user.id}`", reply_markup=kb_cancel("main_menu", "« Назад"), parse_mode="Markdown")