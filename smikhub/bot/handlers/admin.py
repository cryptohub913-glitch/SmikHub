from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.db.models import Bot, Order
from smikhub.bot.admin_guard import is_admin

router = Router()


class AdminInspectState(StatesGroup):
    waiting_for_username = State()


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика всех ботов", callback_data="admin:bots_stats"),
                InlineKeyboardButton(text="🔍 Проверить бота (@user)", callback_data="admin:inspect_prompt"),
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:refresh"),
            ]
        ]
    )


@router.message(F.text.in_(["/admin", "/adm", "Админка"]))
async def cmd_admin_panel(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    text = (
        "👑 **Панель управления SmikHub**\n\n"
        "Здесь доступна статистика сети подключенных ботов "
        "и аудит причин, почему у конкретного бота не отображаются задания."
    )
    await message.answer(text, reply_markup=admin_keyboard(), parse_mode="Markdown")


@router.callback_query(F.data.in_(["admin:bots_stats", "admin:refresh"]))
async def view_bots_stats(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return

    total_bots = await session.scalar(select(func.count(Bot.id))) or 0
    active_bots = await session.scalar(
        select(func.count(Bot.id)).where(getattr(Bot, "is_active", True) == True)
    ) or 0
    paused_bots = total_bots - active_bots

    active_orders = await session.scalar(
        select(func.count(Order.id)).where(
            Order.status == "active",
            getattr(Order, "remaining_budget", 1) > 0
        )
    ) or 0

    text = (
        "📊 **Сводка по сети ботов SmikHub**\n\n"
        f"🤖 Всего добавлено ботов: **{total_bots}**\n"
        f"🟢 Активных (раздают задания): **{active_bots}**\n"
        f"⏸ На паузе у владельцев: **{paused_bots}**\n"
        f"🛍 Активных заказов биржи с балансом: **{active_orders}**\n\n"
        "💡 _Отправь @username бота в чат для вывода аудита настроек._"
    )

    try:
        await callback.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=admin_keyboard(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "admin:inspect_prompt")
async def ask_username_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return

    await state.set_state(AdminInspectState.waiting_for_username)
    await callback.message.answer(
        "✍️ **Отправь `@username` бота** (например, `@test_bot`), чтобы проверить параметры выдачи:",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(AdminInspectState.waiting_for_username)
async def process_fsm_username(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await run_bot_diagnostics(message, message.text.strip(), session)


@router.message(F.text.regexp(r"^@?[a-zA-Z0-9_]{3,35}(bot|Bot|_bot)?$"))
async def process_direct_username(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    await run_bot_diagnostics(message, message.text.strip(), session)


async def run_bot_diagnostics(message: Message, input_text: str, session: AsyncSession):
    clean_username = input_text.lstrip("@").lower().strip()

    bot_query = select(Bot).where(
        or_(
            func.lower(getattr(Bot, "username", Bot.id)) == clean_username,
            func.lower(getattr(Bot, "bot_username", Bot.id)) == clean_username,
        )
    )
    bot = await session.scalar(bot_query)

    active_orders_count = await session.scalar(
        select(func.count(Order.id)).where(
            Order.status == "active",
            getattr(Order, "remaining_budget", 1) > 0
        )
    ) or 0

    if not bot:
        text = (
            f"❌ **Бот `@{clean_username}` не найден в SmikHub!**\n\n"
            "• Бот не зарегистрирован через раздел «Продать ОП».\n"
            "• При вызовах API бот получает ответ `401 Unauthorized` из-за некорректного токена."
        )
        await message.answer(text, reply_markup=admin_keyboard(), parse_mode="Markdown")
        return

    is_active = getattr(bot, "is_active", True)
    min_price = getattr(bot, "min_price", 0.0) or 0.0
    max_sponsors = getattr(bot, "max_sponsors", 3)
    owner_id = getattr(bot, "user_id", "неизвестен")
    providers = getattr(bot, "provider_priority", ["botohub", "flyer", "tgrass"])

    reasons = []

    if not is_active:
        reasons.append("🔴 **Бот на паузе**: в панели включен статус «Приостановить», API возвращает 401.")

    if min_price > 2.0:
        reasons.append(f"⚠️ **Высокий порог min_price ({min_price})**: дешевые офферы отсекаются фильтром.")

    if active_orders_count == 0:
        reasons.append("ℹ️ **Внутренних заказов 'botohub' нет**: задания зависят исключительно от внешних сетей.")

    if not reasons:
        reasons.append(
            "🟢 **Конфигурация в порядке.** Если задания не приходят (`[]`):\n"
            "• Внешние сети (Flyer/Tgrass/PiarFlow) исчерпали лимиты под язык/гео пользователя.\n"
            "• Пользователь уже подписался на все доступные каналы.\n"
            "• Владелец не настроил API-ключи рекламных сетей в кабинете."
        )

    status_badge = "🟢 Активен" if is_active else "⏸ На паузе"
    reasons_text = "\n\n".join(reasons)

    report = (
        f"🤖 **Диагностика бота:** `@{clean_username}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"• **Статус:** {status_badge}\n"
        f"• **ID владельца:** `{owner_id}`\n"
        f"• **Мин. цена:** `{min_price}`\n"
        f"• **Макс. спонсоров:** `{max_sponsors}`\n"
        f"• **Провайдеры:** `{providers}`\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🧠 **Анализ выдачи заданий:**\n\n{reasons_text}"
    )

    await message.answer(report, reply_markup=admin_keyboard(), parse_mode="Markdown")
