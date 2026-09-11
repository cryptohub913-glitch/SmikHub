from decimal import Decimal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from smikhub.bot.callback_data import (
    AddBotCB,
    AdminCategoryCB,
    AdminMenuCB,
    AdminSettingsCB,
    AdminStatsCB,
    AdminUserCB,
    AdminWithdrawalCB,
    BotCB,
    BuyApCB,
    CabinetCB,
    CategoryModeCB,
    DeleteCB,
    DepositCheckCB,
    DisabledCategoryCB,
    IntegrationCB,
    IntegrationsCheckCB,
    MenuCB,
    OrderCategoryCB,
    OrderCB,
    OrderCountryCB,
    OrderDeleteCB,
    OrderGenderCB,
    OrderAgeCB,
    OrderLanguageCB,
    OrderLogCB,
    OrderPlacesCB,
    OrderPremiumCB,
    OrderPriceCB,
    OrderSettingsCB,
    OrderStatsCB,
    OrderVerifyAdminCB,
    PriceCB,
    PriorityCB,
    SponsorsCB,
    StatsCB,
    TokenCB,
)
from smikhub.bot.texts import (
    AGE_GROUP_TITLES,
    GENDER_TITLES,
    PREMIUM_FILTER_TITLES,
    admin_ban_button_label,
    admin_field_button_label,
    age_group_label,
    gender_label,
    order_summary_line,
    premium_filter_label,
)
from smikhub.constants import (
    COUNTRIES,
    LANGUAGES,
    ORDER_PRICE_STEP,
    PRICE_STEP,
    PROVIDER_TITLES,
    price_range,
)
from smikhub.db.models import (
    AgeGroup,
    Category,
    CategoryMode,
    Gender,
    ManagedBot,
    Order,
    PlatformSettings,
    PremiumFilter,
    Provider,
    User,
    WithdrawalRequest,
)
from smikhub.db.platform_repo import EDITABLE_NUMERIC_FIELDS


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🤖 Продать ОП", callback_data=MenuCB(target="sell_ap"))
    builder.button(text="🛍 Купить ОП", callback_data=MenuCB(target="buy_ap"))
    builder.button(text="🎴 Кабинет", callback_data=MenuCB(target="cabinet"))
    builder.adjust(1)
    return builder.as_markup()


def sell_ap_empty_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ добавить бота", callback_data=AddBotCB(action="method"))
    builder.button(text="« Главное меню", callback_data=MenuCB(target="main"))
    builder.adjust(1)
    return builder.as_markup()


def sell_ap_list_kb(bots: list[ManagedBot]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for bot in bots:
        builder.button(text=f"🤖 @{bot.username}", callback_data=BotCB(action="open", bot_id=bot.id))
    builder.button(text="➕ добавить бота", callback_data=AddBotCB(action="method"))
    builder.button(text="« Главное меню", callback_data=MenuCB(target="main"))
    builder.adjust(1)
    return builder.as_markup()


def add_bot_method_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔑 добавить токен", callback_data=AddBotCB(action="token"))
    builder.button(text="« Назад", callback_data=MenuCB(target="sell_ap"))
    builder.adjust(1)
    return builder.as_markup()


def add_bot_token_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="< отмена", callback_data=AddBotCB(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def bot_panel_kb(bot: ManagedBot) -> InlineKeyboardMarkup:
    connected = {i.provider for i in bot.integrations}
    pause_text = "⏸️ Приостановить" if bot.is_active else "▶️ Запустить"

    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Все тематики", callback_data=CategoryModeCB(action="show", bot_id=bot.id))
    builder.button(
        text=f"💰 Мин. цена: {bot.min_price} ₽", callback_data=PriceCB(action="show", bot_id=bot.id)
    )
    builder.button(
        text=f"🔥 Макс. спонсоров: {bot.max_sponsors}",
        callback_data=SponsorsCB(action="show", bot_id=bot.id),
    )
    builder.button(
        text=f"🚫 Отключено: {len(bot.disabled_categories)}",
        callback_data=DisabledCategoryCB(action="show", bot_id=bot.id),
    )
    for provider in Provider:
        mark = "✅" if provider in connected else "⚪"
        builder.button(
            text=f"{mark} {PROVIDER_TITLES[provider.value]}",
            callback_data=IntegrationCB(action="show", bot_id=bot.id, provider=provider.value),
        )
    provider_rows = [2] * ((len(Provider) + 1) // 2)

    builder.button(text="🔀 Приоритет", callback_data=PriorityCB(action="show", bot_id=bot.id))
    builder.button(text="🔑 Токен интеграции", callback_data=TokenCB(bot_id=bot.id))
    builder.button(text="📈 Статистика", callback_data=StatsCB(bot_id=bot.id))
    builder.button(text="🩺 Проверить интеграции", callback_data=IntegrationsCheckCB(bot_id=bot.id))
    builder.button(text=pause_text, callback_data=BotCB(action="toggle_active", bot_id=bot.id))
    builder.button(text="🗑️ Удалить", callback_data=DeleteCB(action="confirm", bot_id=bot.id))
    builder.button(text="🔄 Обновить", callback_data=BotCB(action="refresh", bot_id=bot.id))
    builder.button(text="« Назад", callback_data=BotCB(action="back", bot_id=bot.id))
    builder.button(text="🏠 Меню", callback_data=MenuCB(target="main"))
    builder.adjust(1, 1, 1, 1, *provider_rows, 1, 1, 1, 1, 1, 1, 1, 2)
    return builder.as_markup()


def category_mode_kb(bot: ManagedBot) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🚫 Все, кроме своих",
        callback_data=CategoryModeCB(action="set", bot_id=bot.id, mode=CategoryMode.ALL_EXCEPT_OWN.value),
    )
    builder.button(
        text="🔥 Только свои тематики",
        callback_data=CategoryModeCB(action="set", bot_id=bot.id, mode=CategoryMode.ONLY_OWN.value),
    )
    builder.button(text="« Назад", callback_data=BotCB(action="open", bot_id=bot.id))
    builder.adjust(1)
    return builder.as_markup()


def _back_button(bot: ManagedBot) -> InlineKeyboardButton:
    return InlineKeyboardButton(text="« Назад", callback_data=BotCB(action="open", bot_id=bot.id).pack())


def price_grid_kb(bot: ManagedBot, settings: PlatformSettings) -> InlineKeyboardMarkup:
    min_value = Decimal(str(settings.sell_price_grid_min))
    max_value = Decimal(str(settings.sell_price_grid_max))
    builder = InlineKeyboardBuilder()
    for value in price_range(min_value, max_value, PRICE_STEP):
        builder.button(
            text=f"{value} ₽", callback_data=PriceCB(action="set", bot_id=bot.id, value=str(value))
        )
    builder.adjust(5)
    builder.row(_back_button(bot))
    return builder.as_markup()


def sponsors_grid_kb(bot: ManagedBot, settings: PlatformSettings) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for value in range(settings.sell_sponsors_grid_min, settings.sell_sponsors_grid_max + 1):
        builder.button(text=str(value), callback_data=SponsorsCB(action="set", bot_id=bot.id, value=value))
    builder.adjust(5)
    builder.row(_back_button(bot))
    return builder.as_markup()


def _toggle_list_kb(
    entries: list[tuple[str, bool, CallbackData]], back_button: InlineKeyboardButton, columns: int = 2
) -> InlineKeyboardMarkup:
    """Сетка переключаемых пунктов (❌ = исключено/выключено) + отдельная строка "Назад"."""
    builder = InlineKeyboardBuilder()
    for label, excluded, callback_data in entries:
        mark = "❌ " if excluded else ""
        builder.button(text=f"{mark}{label}", callback_data=callback_data)
    builder.adjust(columns)
    builder.row(back_button)
    return builder.as_markup()


def disabled_categories_kb(bot: ManagedBot, categories: list[Category]) -> InlineKeyboardMarkup:
    disabled_ids = {dc.category_id for dc in bot.disabled_categories}
    entries = [
        (
            category.title,
            category.id in disabled_ids,
            DisabledCategoryCB(action="toggle", bot_id=bot.id, category_id=category.id),
        )
        for category in categories
    ]
    return _toggle_list_kb(entries, _back_button(bot))


def integration_kb(bot: ManagedBot, provider: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if provider == Provider.PIARFLOW.value:
        # PiarFlow можно подключить в одно касание — у нас уже есть и токен бота, и
        # Telegram ID владельца, вставлять ключ вручную не обязательно (см. интеграции).
        builder.button(
            text="🔗 Подключить автоматически",
            callback_data=IntegrationCB(action="auto_connect", bot_id=bot.id, provider=provider),
        )
    builder.button(text="« Назад", callback_data=BotCB(action="open", bot_id=bot.id))
    builder.adjust(1)
    return builder.as_markup()


def priority_kb(bot: ManagedBot) -> InlineKeyboardMarkup:
    ordered = sorted(bot.priorities, key=lambda p: p.position)
    builder = InlineKeyboardBuilder()
    for index, item in enumerate(ordered):
        title = PROVIDER_TITLES.get(item.provider, item.provider)
        row = [
            InlineKeyboardButton(
                text=f"{index + 1}. {title}",
                callback_data=PriorityCB(action="show", bot_id=bot.id).pack(),
            )
        ]
        if index > 0:
            row.append(
                InlineKeyboardButton(
                    text="⬆️",
                    callback_data=PriorityCB(
                        action="move", bot_id=bot.id, provider=item.provider, direction=-1
                    ).pack(),
                )
            )
        if index < len(ordered) - 1:
            row.append(
                InlineKeyboardButton(
                    text="⬇️",
                    callback_data=PriorityCB(
                        action="move", bot_id=bot.id, provider=item.provider, direction=1
                    ).pack(),
                )
            )
        builder.row(*row)
    builder.row(_back_button(bot))
    return builder.as_markup()


def token_kb(bot: ManagedBot) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="« Назад", callback_data=BotCB(action="open", bot_id=bot.id))
    builder.adjust(1)
    return builder.as_markup()


def stats_kb(bot: ManagedBot) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="« Назад", callback_data=BotCB(action="open", bot_id=bot.id))
    builder.adjust(1)
    return builder.as_markup()


def delete_confirm_kb(bot: ManagedBot) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=DeleteCB(action="yes", bot_id=bot.id))
    builder.button(text="❌ Отмена", callback_data=DeleteCB(action="cancel", bot_id=bot.id))
    builder.adjust(1)
    return builder.as_markup()


def delete_success_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="« Назад", callback_data=MenuCB(target="sell_ap"))
    builder.button(text="« Главное меню", callback_data=MenuCB(target="main"))
    builder.adjust(1)
    return builder.as_markup()


# ---- Купить ОП ----


def buy_ap_empty_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать заказ", callback_data=BuyApCB(step="create"))
    builder.button(text="« Главное меню", callback_data=MenuCB(target="main"))
    builder.adjust(1)
    return builder.as_markup()


def buy_ap_list_kb(orders: list[Order]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for order in orders:
        builder.button(text=order_summary_line(order), callback_data=OrderCB(action="open", order_id=order.id))
    builder.button(text="➕ Создать заказ", callback_data=BuyApCB(step="create"))
    builder.button(text="« Главное меню", callback_data=MenuCB(target="main"))
    builder.adjust(1)
    return builder.as_markup()


def buy_ap_traffic_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Подписки", callback_data=BuyApCB(step="traffic", value="subscriptions"))
    builder.button(text="Показы", callback_data=BuyApCB(step="traffic", value="views"))
    builder.button(text="« Назад", callback_data=MenuCB(target="buy_ap"))
    builder.adjust(2, 1)
    return builder.as_markup()


def buy_ap_destination_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Канал/чат", callback_data=BuyApCB(step="destination", value="channel_chat"))
    builder.button(text="Бот", callback_data=BuyApCB(step="destination", value="bot"))
    builder.button(text="Ресурс (без проверки)", callback_data=BuyApCB(step="destination", value="resource"))
    builder.button(text="« Назад", callback_data=MenuCB(target="buy_ap"))
    builder.adjust(1)
    return builder.as_markup()


def buy_ap_cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="< отмена", callback_data=BuyApCB(step="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def order_cancel_kb(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="< отмена", callback_data=OrderCB(action="open", order_id=order_id))
    builder.adjust(1)
    return builder.as_markup()


def order_admin_kb(order: Order, check_bot_username: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить в канал/чат",
            url=f"https://t.me/{check_bot_username}?startchannel=&admin=invite_users+manage_chat",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить в канал (запасная кнопка)",
            url=f"https://t.me/{check_bot_username}?startgroup=&admin=invite_users+manage_chat",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✅ Я добавил бота в администраторы",
            callback_data=OrderVerifyAdminCB(order_id=order.id).pack(),
        )
    )
    return builder.as_markup()


def _order_back_button(order: Order) -> InlineKeyboardButton:
    return InlineKeyboardButton(text="« Назад", callback_data=OrderCB(action="open", order_id=order.id).pack())


def order_panel_kb(order: Order) -> InlineKeyboardMarkup:
    pause_text = "⏸️ Остановить" if order.status.value == "running" else "▶️ Запустить"

    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить статистику", callback_data=OrderStatsCB(order_id=order.id))
    builder.button(text="📜 Лог начислений", callback_data=OrderLogCB(order_id=order.id))
    builder.button(
        text=f"💰 Цена: {order.price} ₽", callback_data=OrderPriceCB(action="show", order_id=order.id)
    )
    builder.button(text="⚙️ Настройки", callback_data=OrderSettingsCB(action="show", order_id=order.id))
    builder.button(text="📍 Места показа", callback_data=OrderPlacesCB(order_id=order.id))
    builder.button(
        text=f"🏷 Тематики: {len(order.excluded_categories)}",
        callback_data=OrderCategoryCB(action="show", order_id=order.id),
    )
    builder.button(text=gender_label(order.gender), callback_data=OrderGenderCB(action="show", order_id=order.id))
    builder.button(text=age_group_label(order.age_group), callback_data=OrderAgeCB(action="show", order_id=order.id))
    builder.button(
        text=premium_filter_label(order.premium_filter),
        callback_data=OrderPremiumCB(action="show", order_id=order.id),
    )
    builder.button(
        text=f"🌐 Языки: {len(order.excluded_languages)}",
        callback_data=OrderLanguageCB(action="show", order_id=order.id),
    )
    builder.button(
        text=f"🌍 Страны: {len(order.excluded_countries)}",
        callback_data=OrderCountryCB(action="show", order_id=order.id),
    )
    builder.button(text=pause_text, callback_data=OrderCB(action="toggle_status", order_id=order.id))
    builder.button(text="🗑️ Удалить", callback_data=OrderDeleteCB(action="confirm", order_id=order.id))
    builder.button(text="« Назад", callback_data=OrderCB(action="back", order_id=order.id))
    builder.button(text="🏠 Меню", callback_data=MenuCB(target="main"))
    builder.adjust(1, 1, 1, 2, 1, 2, 2, 1, 2, 1, 2)
    return builder.as_markup()


def order_price_grid_kb(order: Order, settings: PlatformSettings) -> InlineKeyboardMarkup:
    min_value = Decimal(str(settings.buy_price_grid_min))
    max_value = Decimal(str(settings.buy_price_grid_max))
    builder = InlineKeyboardBuilder()
    for value in price_range(min_value, max_value, ORDER_PRICE_STEP):
        builder.button(
            text=f"{value} ₽", callback_data=OrderPriceCB(action="set", order_id=order.id, value=str(value))
        )
    builder.adjust(5)
    builder.row(_order_back_button(order))
    return builder.as_markup()


def order_categories_kb(order: Order, categories: list[Category]) -> InlineKeyboardMarkup:
    excluded_ids = {c.category_id for c in order.excluded_categories}
    entries = [
        (
            category.title,
            category.id in excluded_ids,
            OrderCategoryCB(action="toggle", order_id=order.id, category_id=category.id),
        )
        for category in categories
    ]
    return _toggle_list_kb(entries, _order_back_button(order))


def order_languages_kb(order: Order) -> InlineKeyboardMarkup:
    excluded_codes = {entry.code for entry in order.excluded_languages}
    entries = [
        (title, code in excluded_codes, OrderLanguageCB(action="toggle", order_id=order.id, code=code))
        for code, title in LANGUAGES
    ]
    return _toggle_list_kb(entries, _order_back_button(order))


def order_countries_kb(order: Order) -> InlineKeyboardMarkup:
    excluded_codes = {entry.code for entry in order.excluded_countries}
    entries = [
        (title, code in excluded_codes, OrderCountryCB(action="toggle", order_id=order.id, code=code))
        for code, title in COUNTRIES
    ]
    return _toggle_list_kb(entries, _order_back_button(order))


def order_gender_kb(order: Order) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for gender in Gender:
        builder.button(
            text=GENDER_TITLES[gender.value],
            callback_data=OrderGenderCB(action="set", order_id=order.id, value=gender.value),
        )
    builder.adjust(1)
    builder.row(_order_back_button(order))
    return builder.as_markup()


def order_age_kb(order: Order) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for age_group in AgeGroup:
        builder.button(
            text=AGE_GROUP_TITLES[age_group.value],
            callback_data=OrderAgeCB(action="set", order_id=order.id, value=age_group.value),
        )
    builder.adjust(1)
    builder.row(_order_back_button(order))
    return builder.as_markup()


def order_premium_kb(order: Order) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for premium_filter in PremiumFilter:
        builder.button(
            text=PREMIUM_FILTER_TITLES[premium_filter.value],
            callback_data=OrderPremiumCB(action="set", order_id=order.id, value=premium_filter.value),
        )
    builder.adjust(1)
    builder.row(_order_back_button(order))
    return builder.as_markup()


def order_settings_kb(order: Order) -> InlineKeyboardMarkup:
    per_day = order.users_per_day if order.users_per_day is not None else "Неважно"
    total = order.users_total if order.users_total is not None else "Неважно"
    distribute = "✅" if order.distribute_during_day else "❌"

    builder = InlineKeyboardBuilder()
    builder.button(text="Изменить ссылку", callback_data=OrderSettingsCB(action="change_link", order_id=order.id))
    builder.button(
        text=f"Пользователей в день: {per_day}",
        callback_data=OrderSettingsCB(action="per_day", order_id=order.id),
    )
    builder.button(
        text=f"Пользователей всего: {total}", callback_data=OrderSettingsCB(action="total", order_id=order.id)
    )
    builder.button(
        text=f"Распределить в течение дня: {distribute}",
        callback_data=OrderSettingsCB(action="toggle_distribute", order_id=order.id),
    )
    builder.adjust(1)
    builder.row(_order_back_button(order))
    return builder.as_markup()


def order_places_kb(order: Order) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_order_back_button(order))
    return builder.as_markup()


def order_stats_kb(order: Order) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_order_back_button(order))
    return builder.as_markup()


def order_log_kb(order: Order) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data=OrderLogCB(order_id=order.id))
    builder.adjust(1)
    builder.row(_order_back_button(order))
    return builder.as_markup()


def order_delete_confirm_kb(order: Order) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=OrderDeleteCB(action="yes", order_id=order.id))
    builder.button(text="❌ Отмена", callback_data=OrderDeleteCB(action="cancel", order_id=order.id))
    builder.adjust(1)
    return builder.as_markup()


def order_delete_success_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="« Назад", callback_data=MenuCB(target="buy_ap"))
    builder.button(text="« Главное меню", callback_data=MenuCB(target="main"))
    builder.adjust(1)
    return builder.as_markup()


# ---- Кабинет ----


def cabinet_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Пополнить", callback_data=CabinetCB(action="deposit"))
    builder.button(text="💸 Вывести", callback_data=CabinetCB(action="withdraw"))
    builder.button(text="« Главное меню", callback_data=MenuCB(target="main"))
    builder.adjust(1)
    return builder.as_markup()


def cabinet_cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="< отмена", callback_data=CabinetCB(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def deposit_invoice_kb(invoice_id: int, pay_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Оплатить", url=pay_url))
    builder.row(
        InlineKeyboardButton(
            text="🔄 Проверить оплату", callback_data=DepositCheckCB(invoice_id=invoice_id).pack()
        )
    )
    builder.row(InlineKeyboardButton(text="« Кабинет", callback_data=MenuCB(target="cabinet").pack()))
    return builder.as_markup()


# ---- Админ-панель ----


def admin_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💸 Заявки на вывод", callback_data=AdminMenuCB(target="withdrawals"))
    builder.button(text="📊 Статистика", callback_data=AdminMenuCB(target="stats"))
    builder.button(text="👥 Пользователи", callback_data=AdminMenuCB(target="users"))
    builder.button(text="⚙️ Настройки", callback_data=AdminMenuCB(target="settings"))
    builder.button(text="🩺 Диагностика", callback_data=AdminMenuCB(target="diagnostics"))
    builder.adjust(1)
    return builder.as_markup()


def admin_back_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="« Назад", callback_data=AdminMenuCB(target="main"))
    builder.adjust(1)
    return builder.as_markup()


def admin_withdrawals_list_kb(requests: list[WithdrawalRequest]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for request in requests:
        builder.button(
            text=f"Заявка #{request.id} — {request.amount}",
            callback_data=AdminWithdrawalCB(action="show", withdrawal_id=request.id),
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="« Назад", callback_data=AdminMenuCB(target="main").pack()))
    return builder.as_markup()


def admin_withdrawal_detail_kb(withdrawal_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить", callback_data=AdminWithdrawalCB(action="approve", withdrawal_id=withdrawal_id))
    builder.button(text="❌ Отклонить", callback_data=AdminWithdrawalCB(action="reject", withdrawal_id=withdrawal_id))
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="« Назад", callback_data=AdminMenuCB(target="withdrawals").pack()))
    return builder.as_markup()


def admin_stats_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🤖 По ботам", callback_data=AdminStatsCB(target="bots"))
    builder.button(text="👥 По пользователям", callback_data=AdminMenuCB(target="users"))
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="« Назад", callback_data=AdminMenuCB(target="main").pack()))
    return builder.as_markup()


def admin_users_search_kb() -> InlineKeyboardMarkup:
    return admin_back_kb()


def admin_user_profile_kb(user: User) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=admin_ban_button_label(user), callback_data=AdminUserCB(action="ban", user_id=user.id))
    builder.button(
        text="💰 Скорректировать баланс", callback_data=AdminUserCB(action="balance", user_id=user.id)
    )
    builder.button(text="🔍 Другой пользователь", callback_data=AdminUserCB(action="search_again"))
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="« Назад", callback_data=AdminMenuCB(target="main").pack()))
    return builder.as_markup()


def admin_settings_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Цены и лимиты", callback_data=AdminSettingsCB(action="show_prices"))
    builder.button(text="🏷 Тематики", callback_data=AdminCategoryCB(action="show"))
    builder.button(text="🔀 Продать ОП вкл/выкл", callback_data=AdminSettingsCB(action="toggle_sell"))
    builder.button(text="🔀 Купить ОП вкл/выкл", callback_data=AdminSettingsCB(action="toggle_buy"))
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="« Назад", callback_data=AdminMenuCB(target="main").pack()))
    return builder.as_markup()


def admin_prices_kb(settings: PlatformSettings) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for field, (label, _kind) in EDITABLE_NUMERIC_FIELDS.items():
        builder.button(
            text=admin_field_button_label(field, label, settings),
            callback_data=AdminSettingsCB(action="edit_field", field=field),
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="« Назад", callback_data=AdminMenuCB(target="settings").pack()))
    return builder.as_markup()


def admin_prices_cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="< отмена", callback_data=AdminSettingsCB(action="show_prices"))
    builder.adjust(1)
    return builder.as_markup()


def admin_categories_kb(categories: list[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(
            text=category.title, callback_data=AdminCategoryCB(action="detail", category_id=category.id)
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="➕ Добавить тематику", callback_data=AdminCategoryCB(action="add").pack()))
    builder.row(InlineKeyboardButton(text="« Назад", callback_data=AdminMenuCB(target="settings").pack()))
    return builder.as_markup()


def admin_categories_cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="< отмена", callback_data=AdminCategoryCB(action="show"))
    builder.adjust(1)
    return builder.as_markup()


def admin_category_detail_kb(category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Переименовать", callback_data=AdminCategoryCB(action="rename", category_id=category_id))
    builder.button(
        text="🗑 Удалить", callback_data=AdminCategoryCB(action="delete_confirm", category_id=category_id)
    )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="« Назад", callback_data=AdminCategoryCB(action="show").pack()))
    return builder.as_markup()


def admin_category_delete_confirm_kb(category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=AdminCategoryCB(action="delete_yes", category_id=category_id))
    builder.button(
        text="❌ Отмена", callback_data=AdminCategoryCB(action="delete_cancel", category_id=category_id)
    )
    builder.adjust(1)
    return builder.as_markup()
