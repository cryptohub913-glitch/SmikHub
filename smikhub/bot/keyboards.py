from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
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


def cabinet_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Пополнить", callback_data="nav:topup_menu"),
            InlineKeyboardButton(text="📤 Вывести", callback_data="nav:withdraw_menu")
        ],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")]
    ])


def topup_methods_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 CryptoBot (USDT / TON)", callback_data="topup:cryptobot")],
        [InlineKeyboardButton(text="⭐️ Telegram Stars", callback_data="topup:stars")],
        [InlineKeyboardButton(text="« Назад в кабинет", callback_data="nav:cabinet")]
    ])


def withdraw_methods_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 SendPay (Карты / СБП)", callback_data="withdraw:sendpay")],
        [InlineKeyboardButton(text="« Назад в кабинет", callback_data="nav:cabinet")]
    ])


def bot_list_kb(bots: list) -> InlineKeyboardMarkup:
    buttons = []
    for b in bots:
        status_icon = "🟢" if getattr(b, "is_approved", True) else "⏳"
        buttons.append([InlineKeyboardButton(text=f"{status_icon} @{b.username}", callback_data=f"bot_manage:{b.id}")])
    buttons.append([InlineKeyboardButton(text="➕ Добавить бота", callback_data="nav:add_bot")])
    buttons.append([InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def bot_settings_kb(bot_id: int) -> InlineKeyboardMarkup:
    """Полная панель настроек бота: цены, лимиты, интеграции (Adsgram, PR Flow, Webhook)."""
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
            InlineKeyboardButton(text="🌐 Сторонние интеграции (Adsgram/PR Flow)", callback_data=f"bot_integrations:{bot_id}")
        ],
        [InlineKeyboardButton(text="❌ Удалить бота", callback_data=f"bot_delete:{bot_id}")],
        [InlineKeyboardButton(text="« Назад к списку ботов", callback_data="nav:sell_traffic")]
    ])


def buy_traffic_kb(orders: list) -> InlineKeyboardMarkup:
    buttons = []
    for o in orders:
        buttons.append([InlineKeyboardButton(text=f"🛍 Заказ #{o.id} ({o.status})", callback_data=f"order_view:{o.id}")])
    buttons.append([InlineKeyboardButton(text="➕ Создать кампанию", callback_data="nav:create_order")])
    buttons.append([InlineKeyboardButton(text="« Назад в меню", callback_data="nav:main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def order_control_kb(order_id: int, status: str, price: float) -> InlineKeyboardMarkup:
    """Точная раскладка кнопок кампании (Скриншот 1)."""
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


def admin_bot_moderation_kb(bot_id: int) -> InlineKeyboardMarkup:
    """Кнопки одобрения/отклонения бота в админке."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve_bot:{bot_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_bot:{bot_id}")
        ]
    ])


def back_kb(target: str = "main_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Назад", callback_data=f"nav:{target}")]
    ])
