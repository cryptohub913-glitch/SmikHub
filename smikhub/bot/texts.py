from smikhub.constants import PROVIDER_TITLES
from smikhub.db.models import (
    AgeGroup,
    Category,
    CategoryMode,
    Gender,
    ManagedBot,
    Order,
    PlatformSettings,
    PremiumFilter,
    User,
)
from smikhub.db.platform_repo import EDITABLE_NUMERIC_FIELDS

IN_DEVELOPMENT = "🚧 Раздел в разработке"
SECTION_DISABLED = "🚧 Раздел временно отключён администратором."

MAIN_MENU = "👋 Добро пожаловать в SmikHub!\n\nВыберите раздел:"

SELL_AP_EMPTY = "🤖 Продать ОП\n\nУ вас пока нет ботов"
SELL_AP_LIST_HEADER = "🤖 Продать ОП\n\nВаши боты:"

ADD_BOT_METHOD = "🤖 Добавить бота\n\nКак вы хотите подключить бота?"

ADD_BOT_TOKEN_PROMPT = (
    "🔑 **Подключение через токен**\n\n"
    "Отправьте токен вашего бота.\n\n"
    "Получить токен можно у @BotFather командой /mybots"
)

ADD_BOT_INVALID_TOKEN = (
    "❌ Не удалось проверить токен. Убедитесь, что он корректный, и отправьте его снова."
)

ADD_BOT_ALREADY_EXISTS = "⚠️ Этот бот уже подключён к платформе. Отправьте токен другого бота."

DELETE_CONFIRM = "🗑 Удаление бота\n\nВы уверены что хотите удалить этого бота?"
DELETE_SUCCESS = "✅ Бот успешно удален."

STATS_NO_PROVIDERS = (
    "📈 Статистика\n\n"
    "Подключите Flyer/Tgrass/PiarFlow (кнопки в панели бота), чтобы видеть здесь реальные "
    "цифры по каждой сети."
)
STATS_UNAVAILABLE = "⚠️ Данные временно недоступны."
STATS_SUBGRAM_UNAVAILABLE = "❄ Subgram\nСтатистика недоступна — по этой сети нет документации API."


def stats_screen(bot: ManagedBot, sections: list[str]) -> str:
    if not sections:
        return STATS_NO_PROVIDERS
    return f"📈 Статистика — @{bot.username}\n\n" + "\n\n".join(sections)


def stats_tgrass_section(stats) -> str:
    balance = stats.balance if stats.balance is not None else "—"
    subs = stats.subs_count if stats.subs_count is not None else "—"
    unsubs = stats.unsubs_count if stats.unsubs_count is not None else "—"
    income = stats.income if stats.income is not None else "—"
    return (
        f"🌱 Tgrass\n"
        f"Баланс: {balance}\n"
        f"Подписок сегодня: {subs}\n"
        f"Отписок сегодня: {unsubs}\n"
        f"Доход сегодня: {income}"
    )


def stats_piarflow_section(stats) -> str:
    balance = stats.balance if stats.balance is not None else "—"
    subs = stats.subs_count if stats.subs_count is not None else "—"
    unsubs = stats.unsubs_count if stats.unsubs_count is not None else "—"
    income = stats.income if stats.income is not None else "—"
    return (
        f"🚀 PiarFlow\n"
        f"Баланс: {balance}\n"
        f"Подписок сегодня: {subs}\n"
        f"Отписок сегодня: {unsubs}\n"
        f"Доход сегодня: {income}"
    )


def stats_flyer_section(info: dict) -> str:
    status = "✅ активен" if info.get("status") else "❌ неактивен"
    bot_id = info.get("bot_id", "—")
    return (
        f"📮 Flyer\n"
        f"Статус ключа: {status}\n"
        f"bot_id: {bot_id}\n"
        f"(агрегированной статистики дохода Flyer через API не отдаёт)"
    )

SUBGRAM_CONNECT = (
    "🔗 Подключение Subgram\n\n"
    "Subgram — это сервис для заработка на обязательных подписках.\n\n"
    "⚠️ Важно: Весь доход от подписок идёт напрямую в Subgram. SmikHub только показывает "
    "спонсоров вашим пользователям и не имеет финансовой связи с доходом от Subgram.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "📋 Обязательные настройки в Subgram:\n\n"
    "• Получать ссылки в API: Вкл.\n"
    "• Показывать анкеты: Выкл.\n"
    "• Пол: Выкл.\n"
    "• Возраст: Выкл.\n\n"
    "⚙️ При других настройках интеграция работать не будет!\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "Отправьте токен от Subgram:"
)

FLYER_CONNECT = (
    "🔗 **Подключение Flyer**\n\n"
    "[Flyer](https://t.me/FlyerServiceBot?start=ref417931442) — это сервис для заработка "
    "на обязательных подписках.\n\n"
    "⚠️ **Важно:** Весь доход от подписок идёт напрямую в Flyer. SmikHub только показывает "
    "спонсоров вашим пользователям и не имеет финансовой связи с доходом от Flyer.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "📝 **Как добавить бота:**\n\n"
    "1. Перейдите в [Flyer](https://t.me/FlyerServiceBot?start=ref417931442)\n"
    "2. Добавьте вашего бота как **ЗАДАНИЯ**\n\n"
    "⚠️ **Не добавляйте бота как «Обязательная подписка»!**\n"
    "Если бот уже добавлен как ОП — удалите и добавьте заново как «Задания».\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "Отправьте токен от Flyer:"
)

TGRASS_CONNECT = (
    "🔗 Подключение Tgrass\n\n"
    "Tgrass — это сервис для заработка на обязательных подписках.\n\n"
    "⚠️ Важно: Весь доход от подписок идёт напрямую в Tgrass. SmikHub только показывает "
    "спонсоров вашим пользователям и не имеет финансовой связи с доходом от Tgrass.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "📝 Как получить ключ:\n\n"
    "1. Перейдите в @tgrassbot\n"
    "2. Зарегистрируйте там своего бота и получите ключ авторизации (Auth)\n\n"
    "⚠️ У Tgrass в его API нет цены за оффер — фильтр «Мин. цена» к его спонсорам "
    "применяться не будет.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "Отправьте ключ от Tgrass:"
)

PIARFLOW_CONNECT = (
    "🔗 Подключение PiarFlow\n\n"
    "PiarFlow — это сервис для заработка на обязательных подписках.\n\n"
    "⚠️ Важно: Весь доход от подписок идёт напрямую в PiarFlow. SmikHub только показывает "
    "спонсоров вашим пользователям и не имеет финансовой связи с доходом от PiarFlow.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "📝 Как получить ключ:\n\n"
    "1. Зарегистрируйте вашего бота в PiarFlow как трафик-бота (раздел для владельцев "
    "ботов на piarflow.com)\n"
    "2. Получите API-ключ бота\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "Отправьте ключ от PiarFlow:"
)

INTEGRATION_TEXTS = {
    "subgram": SUBGRAM_CONNECT,
    "flyer": FLYER_CONNECT,
    "tgrass": TGRASS_CONNECT,
    "piarflow": PIARFLOW_CONNECT,
}
INTEGRATION_INVALID_TOKEN = "❌ Не удалось сохранить токен, попробуйте отправить его снова."

PIARFLOW_AUTO_CONNECT_FAILED = (
    "❌ Не удалось подключить автоматически. Пришлите ключ вручную (см. инструкцию выше)."
)
PIARFLOW_AUTO_CONNECT_SUCCESS = "✅ PiarFlow подключён автоматически!"


def bot_panel(bot: ManagedBot) -> str:
    status = "🟢 Активен" if bot.is_active else "⏸ Приостановлен"
    return f"🤖 @{bot.username}\n\nСтатус: {status}"


def category_mode_screen(bot: ManagedBot) -> str:
    return f"📊 Тематики спонсоров\n\n🤖 @{bot.username}\n\nВыберите режим показа тематик:"


def min_price_screen(bot: ManagedBot) -> str:
    return f"💰 Минимальная цена\n\n🤖 @{bot.username}\nТекущая: {bot.min_price} ₽"


def max_sponsors_screen(bot: ManagedBot) -> str:
    return f"🔥 Максимум спонсоров\n\n🤖 @{bot.username} настройки\nТекущее: {bot.max_sponsors}"


def disabled_categories_screen(bot: ManagedBot) -> str:
    return (
        f"🚫 Отключенные тематики\n\n🤖 @{bot.username}\nОтключено: {len(bot.disabled_categories)}"
    )


def priority_screen(bot: ManagedBot) -> str:
    return f"🔀 Приоритет сервисов\n\n🤖 @{bot.username}\n\nСервисы выше имеют больший приоритет при выдаче спонсоров."


def integration_token_screen(bot: ManagedBot, token: str) -> str:
    return (
        f"🔑 Токен интеграции\n\n🤖 @{bot.username}\n\n`{token}`\n\n"
        "Используйте этот токен в заголовке Auth для авторизации API запросов."
    )


def category_mode_label(mode: CategoryMode) -> str:
    return "🔥 Только свои тематики" if mode == CategoryMode.ONLY_OWN else "🚫 Все, кроме своих"


# ---- Купить ОП ----

BUY_AP_EMPTY = "🛍 Купить ОП\n\nУ вас пока нет заказов"
BUY_AP_LIST_HEADER = "🛍 Купить ОП\n\nВаши заказы:"
BUY_AP_TRAFFIC_PROMPT = "🛍 Купить ОП\n\nКакой трафик хотите купить?"

TRAFFIC_TYPE_TITLES = {"subscriptions": "Подписки", "views": "Показы"}
DESTINATION_TYPE_TITLES = {
    "channel_chat": "Канал/чат",
    "bot": "Бот",
    "resource": "Ресурс (без проверки)",
}
ORDER_STATUS_TITLES = {"paused": "🔴 Остановлено", "running": "🟢 Активен"}
GENDER_TITLES = {"any": "Любой", "male": "Мужской", "female": "Женский"}
AGE_GROUP_TITLES = {"any": "Любой возраст", "under_13": "до 13", "age_14_17": "14-17", "adult": "18+"}
PREMIUM_FILTER_TITLES = {"not_important": "Не важно", "only_premium": "Только"}

DESTINATION_LINK_PROMPTS = {
    "channel_chat": (
        "Пришлите публичную ссылку на ваш канал или чат (вида t.me/username).\n\n"
        "Пока поддерживаются только публичные ссылки — по ним check-бот сможет "
        "проверить админ-доступ и реальные вступления."
    ),
    "bot": "Пришлите токен бота, в который нужно привести пользователей.",
    "resource": "Пришлите ссылку на сайт или страницу, куда нужно привести трафик.",
}

BUY_AP_INVALID_LINK = "❌ Не похоже на публичную ссылку вида t.me/username. Пришлите её ещё раз."
BUY_AP_INVALID_BOT_TOKEN = "❌ Не удалось проверить токен бота. Убедитесь, что он корректный."
BUY_AP_INVALID_RESOURCE_LINK = "❌ Пришлите корректную ссылку (начинается с http:// или https://)."

ORDER_ADMIN_NOT_CONFIRMED = (
    "❌ Не вижу check-бота в администраторах этого чата. Добавьте его и попробуйте снова."
)
ORDER_CHECK_BOT_NOT_CONFIGURED = (
    "⚠️ Check-бот платформы ещё не настроен администратором — заказ создан, но проверка "
    "реальных вступлений и списание за них пока недоступны."
)

DELETE_ORDER_CONFIRM = "🗑 Удаление заказа\n\nВы уверены что хотите удалить этот заказ?"
DELETE_ORDER_SUCCESS = "✅ Заказ успешно удалён."

ORDER_SETTINGS_LINK_PROMPT = "Пришлите новую ссылку/токен назначения."
ORDER_SETTINGS_USERS_PER_DAY_PROMPT = "Отправьте число пользователей в день или 0, чтобы снять лимит."
ORDER_SETTINGS_USERS_TOTAL_PROMPT = "Отправьте общее число пользователей или 0, чтобы снять лимит."
ORDER_SETTINGS_INVALID_NUMBER = "❌ Пришлите целое неотрицательное число."

ORDER_PLACES = f"📍 Места показа\n\n{IN_DEVELOPMENT}"


def destination_prompt(traffic_type: str) -> str:
    noun = "подписчиков" if traffic_type == "subscriptions" else "показы"
    return f"Куда привести {noun}?"


def order_admin_prompt(check_bot_username: str) -> str:
    return (
        f"Добавьте @{check_bot_username} в администраторы канала или чата.\n\n"
        "Это нужно для проверки вступлений и отписок."
    )


def order_summary_line(order: Order) -> str:
    traffic = TRAFFIC_TYPE_TITLES[order.traffic_type.value]
    destination = DESTINATION_TYPE_TITLES[order.destination_type.value]
    return f"#{order.id} · {traffic} · {destination}"


def order_panel(order: Order) -> str:
    status = ORDER_STATUS_TITLES[order.status.value]
    traffic = TRAFFIC_TYPE_TITLES[order.traffic_type.value]
    destination = DESTINATION_TYPE_TITLES[order.destination_type.value]
    return (
        f"🛍 Заказ #{order.id}\n\n"
        f"Трафик: {traffic}\n"
        f"Назначение: {destination}\n"
        f"Статус: {status}\n"
        f"Цена: {order.price} ₽\n"
        f"Потрачено: {order.spent} ₽"
    )


def order_price_screen(order: Order) -> str:
    return f"💰 Цена заказа #{order.id}\n\nТекущая: {order.price} ₽"


def order_categories_screen(order: Order) -> str:
    return f"🏷 Тематики\n\nЗаказ #{order.id}\nИсключено: {len(order.excluded_categories)}"


def order_languages_screen(order: Order) -> str:
    return f"🌐 Языки интерфейса\n\nЗаказ #{order.id}\nИсключено: {len(order.excluded_languages)}"


def order_countries_screen(order: Order) -> str:
    return f"🌍 Страны\n\nЗаказ #{order.id}\nИсключено: {len(order.excluded_countries)}"


def order_gender_screen(order: Order) -> str:
    return f"🚻 Пол\n\nЗаказ #{order.id}\nТекущий: {GENDER_TITLES[order.gender.value]}"


def order_age_screen(order: Order) -> str:
    return f"🎂 Возраст\n\nЗаказ #{order.id}\nТекущий: {AGE_GROUP_TITLES[order.age_group.value]}"


def order_premium_screen(order: Order) -> str:
    return f"💎 TG Premium\n\nЗаказ #{order.id}\nТекущий: {PREMIUM_FILTER_TITLES[order.premium_filter.value]}"


def order_settings_screen(order: Order) -> str:
    per_day = order.users_per_day if order.users_per_day is not None else "Неважно"
    total = order.users_total if order.users_total is not None else "Неважно"
    distribute = "Да ✅" if order.distribute_during_day else "Нет ❌"
    return (
        f"⚙️ Настройки заказа #{order.id}\n\n"
        f"Ссылка/токен: {order.destination_link}\n"
        f"Пользователей в день: {per_day}\n"
        f"Пользователей всего: {total}\n"
        f"Распределить в течение дня: {distribute}"
    )


def order_stats_screen(order: Order, stats: dict) -> str:
    return (
        f"📈 Статистика заказа #{order.id}\n\n"
        f"Пользователи\n"
        f"Всего: {stats['total']}\n"
        f"За сегодня: {stats['today']}\n"
        f"Удержание: {stats['retention']}\n\n"
        f"Финансы\n"
        f"Потрачено: {order.spent} ₽"
    )


ORDER_LOG_EMPTY = "📜 Лог начислений\n\nПока нет начислений."
ORDER_LOG_RESOURCE_CONFIRMED = "✅ resource_unlock"
ORDER_LOG_RESOURCE_PENDING = "⏳ бот ещё не подтверждён администратором чата"


def order_log_screen(order: Order, events: list, quality_pct, non_quality_pct) -> str:
    if not events:
        return f"📜 Лог начислений — Заказ #{order.id}\n\n{ORDER_LOG_EMPTY}"

    resource_status = (
        ORDER_LOG_RESOURCE_CONFIRMED if order.target_chat_id is not None else ORDER_LOG_RESOURCE_PENDING
    )

    entries = []
    for index, event in enumerate(events, start=1):
        user_line = f"👤 {event.telegram_user_id}"
        if event.telegram_username:
            user_line += f" (@{event.telegram_username})"
        entries.append(
            f"{index}. 💰 Начисление\n"
            f"{event.price} ₽ · {order.destination_link}\n"
            f"{user_line}\n"
            f"{resource_status}\n"
            f"🕒 {event.joined_at:%Y-%m-%d %H:%M}"
        )

    quality_line = f"📊 Качество (оценка платформы): {quality_pct}% / некач. {non_quality_pct}%"
    header = f"📜 Лог начислений — Заказ #{order.id}\n\n{quality_line}\n"
    return header + "\n\n" + "\n\n".join(entries)


def gender_label(gender: Gender) -> str:
    return f"🚻 Пол: {GENDER_TITLES[gender.value]}"


def age_group_label(age_group: AgeGroup) -> str:
    return f"🎂 Возраст: {AGE_GROUP_TITLES[age_group.value]}"


def premium_filter_label(premium_filter: PremiumFilter) -> str:
    return f"💎 TG Premium: {PREMIUM_FILTER_TITLES[premium_filter.value]}"


# ---- Кабинет ----

ASSET = "USDT"

DEPOSIT_INVALID_AMOUNT = "❌ Пришлите положительное число."
DEPOSIT_SERVICE_UNAVAILABLE = (
    "⚠️ Пополнение временно недоступно — сервис оплаты не настроен. Попробуйте позже."
)
DEPOSIT_CREATE_FAILED = "❌ Не удалось создать счёт на оплату. Попробуйте позже."
DEPOSIT_STILL_PENDING = "⏳ Оплата ещё не поступила. Если вы уже оплатили — подождите и проверьте снова."
DEPOSIT_ALREADY_CREDITED = "✅ Уже зачислено ранее."

WITHDRAWAL_REQUEST_CREATED = "✅ Заявка на вывод создана и отправлена на рассмотрение администратору."
WITHDRAWAL_SERVICE_UNAVAILABLE = (
    "⚠️ Вывод временно недоступен — сервис выплат не настроен. Попробуйте позже."
)


def cabinet_screen(user: User) -> str:
    return f"🎴 Кабинет\n\nВаш баланс: {user.balance} {ASSET}"


def deposit_amount_prompt(min_amount) -> str:
    return f"💰 Пополнение баланса\n\nОтправьте сумму пополнения в {ASSET} (минимум {min_amount})."


def deposit_amount_too_small(min_amount) -> str:
    return f"❌ Минимальная сумма пополнения — {min_amount} {ASSET}."


def deposit_invoice_created(amount) -> str:
    return (
        f"💳 Счёт на {amount} {ASSET} создан.\n\n"
        "Оплатите по кнопке ниже, затем нажмите «Проверить оплату»."
    )


def withdrawal_amount_prompt(balance, min_amount) -> str:
    return (
        f"💸 Вывод средств\n\nВаш баланс: {balance} {ASSET}\n"
        f"Минимальная сумма вывода: {min_amount} {ASSET}\n\nОтправьте сумму вывода."
    )


def withdrawal_amount_invalid(balance, min_amount) -> str:
    return f"❌ Сумма должна быть от {min_amount} до {balance} {ASSET}."


def withdrawal_admin_notification(request_id: int, telegram_user_id: int, amount) -> str:
    return (
        f"💸 Новая заявка на вывод #{request_id}\n\n"
        f"Пользователь: {telegram_user_id}\nСумма: {amount} {ASSET}"
    )


# ---- Админ-панель ----

ADMIN_MENU = "🛠 Админ-панель\n\nВыберите раздел:"

ADMIN_WITHDRAWALS_EMPTY = "💸 Заявки на вывод\n\nНет ожидающих заявок."
ADMIN_WITHDRAWALS_HEADER = "💸 Заявки на вывод\n\nОжидающие:"

WITHDRAWAL_APPROVED = "✅ Заявка одобрена, выплата отправлена."
WITHDRAWAL_REJECTED = "❌ Заявка отклонена, баланс возвращён пользователю."

ADMIN_USER_SEARCH_PROMPT = "👥 Управление пользователями\n\nПришлите Telegram ID пользователя."
ADMIN_USER_NOT_FOUND = "❌ Пользователь с таким ID не найден."
ADMIN_INVALID_ID = "❌ Пришлите числовой Telegram ID."

ADMIN_BALANCE_DELTA_PROMPT = "💰 Отправьте сумму коррекции баланса (можно с минусом, например -5 или 10)."
ADMIN_BALANCE_DELTA_INVALID = "❌ Пришлите число, например 10 или -5.5"

ADMIN_INVALID_AMOUNT = "❌ Пришлите положительное число."

ADMIN_CATEGORY_ADD_PROMPT = "🏷 Отправьте название новой тематики."
ADMIN_CATEGORY_RENAME_PROMPT = "✏️ Отправьте новое название тематики."
ADMIN_CATEGORY_INVALID_TITLE = "❌ Название не может быть пустым."
ADMIN_CATEGORY_DELETE_CONFIRM = "🗑 Удалить эту тематику? Она пропадёт из фильтров всех ботов и заказов."
ADMIN_CATEGORY_NOT_FOUND = "❌ Тематика не найдена."


def withdrawal_transfer_failed(error: str) -> str:
    return f"⚠️ Ошибка Send API при выплате: {error}\n\nЗаявка остаётся в ожидании."


def withdrawal_detail(request, telegram_user_id: int) -> str:
    return (
        f"💸 Заявка #{request.id}\n\n"
        f"Пользователь: {telegram_user_id}\n"
        f"Сумма: {request.amount} {ASSET}\n"
        f"Создана: {request.created_at:%Y-%m-%d %H:%M}"
    )


def admin_stats_screen(stats: dict) -> str:
    return (
        "📊 Статистика платформы\n\n"
        f"Пользователей: {stats['users_count']}\n"
        f"Ботов подключено: {stats['bots_count']}\n"
        f"Заказов создано: {stats['orders_count']}\n\n"
        f"Оборот по заказам: {stats['total_spent']} ₽\n"
        f"Пополнено всего: {stats['total_deposits']} {ASSET}\n"
        f"Выведено всего: {stats['total_withdrawals']} {ASSET}"
    )


def admin_bots_list_screen(bots: list[ManagedBot]) -> str:
    if not bots:
        return "🤖 Боты платформы\n\nПока нет подключённых ботов."
    lines = [
        f"@{bot.username} — владелец {bot.owner_id} — {'🟢' if bot.is_active else '⏸'}" for bot in bots
    ]
    return f"🤖 Боты платформы (последние {len(bots)})\n\n" + "\n".join(lines)


def admin_user_profile(stats: dict) -> str:
    user: User = stats["user"]
    ban_status = "🚫 Забанен" if user.is_banned else "🟢 Активен"
    return (
        f"👤 Пользователь {user.id}\n\n"
        f"Статус: {ban_status}\n"
        f"Баланс: {user.balance} {ASSET}\n"
        f"Ботов: {stats['bots_count']}\n"
        f"Заказов: {stats['orders_count']}\n"
        f"Потрачено на заказы: {stats['total_spent']} ₽\n"
        f"Пополнений: {stats['deposits_paid']}\n"
        f"Выводов одобрено: {stats['withdrawals_approved']}\n"
        f"Регистрация: {user.created_at:%Y-%m-%d}"
    )


def admin_ban_button_label(user: User) -> str:
    return "✅ Разбанить" if user.is_banned else "🚫 Забанить"


def admin_balance_adjusted(user: User) -> str:
    return f"✅ Баланс изменён. Текущий баланс: {user.balance} {ASSET}"


def admin_settings_screen(
    settings: PlatformSettings, send_configured: bool, check_bot_configured: bool
) -> str:
    send_status = "✅ настроен" if send_configured else "❌ не настроен"
    check_status = "✅ настроен" if check_bot_configured else "❌ не настроен"
    sell_status = "🟢 включено" if settings.sell_ap_enabled else "🚫 выключено"
    buy_status = "🟢 включено" if settings.buy_ap_enabled else "🚫 выключено"
    return (
        "⚙️ Настройки платформы\n\n"
        f"Продать ОП: {sell_status}\n"
        f"Купить ОП: {buy_status}\n\n"
        f"Интеграции:\n"
        f"Send Pay: {send_status}\n"
        f"Check-бот: {check_status}"
    )


def admin_prices_screen(settings: PlatformSettings) -> str:
    lines = [
        f"{label} — {getattr(settings, field)}" for field, (label, _kind) in EDITABLE_NUMERIC_FIELDS.items()
    ]
    return "💰 Цены и лимиты\n\n" + "\n".join(lines)


def admin_field_button_label(field: str, label: str, settings: PlatformSettings) -> str:
    return f"{label}: {getattr(settings, field)}"


def admin_edit_field_prompt(label: str) -> str:
    return f"✏️ {label}\n\nОтправьте новое значение."


def admin_categories_screen(categories: list[Category]) -> str:
    if not categories:
        return "🏷 Тематики\n\nСписок пуст."
    lines = [f"• {category.title}" for category in categories]
    return "🏷 Тематики\n\n" + "\n".join(lines)


# ---- Диагностика ----


def admin_diagnostics_db_ok(stats: dict) -> str:
    return (
        "🗄 База данных: ✅ ок\n"
        f"Пользователей: {stats['users_count']} · Ботов: {stats['bots_count']} · "
        f"Заказов: {stats['orders_count']}"
    )


def admin_diagnostics_db_error(error: str) -> str:
    return f"🗄 База данных: ❌ ошибка\n{error}"


DIAGNOSTICS_CHECK_BOT_NOT_CONFIGURED = "📡 Check-бот: ⚪ не настроен (CHECK_BOT_TOKEN пуст)"
DIAGNOSTICS_CHECK_BOT_ERROR = "📡 Check-бот: ❌ не отвечает (неверный токен или недоступен Telegram API)"


def admin_diagnostics_check_bot_ok(username: str) -> str:
    return f"📡 Check-бот: ✅ @{username}"


DIAGNOSTICS_SEND_PAY_NOT_CONFIGURED = "💳 Send Pay: ⚪ не настроен (SEND_API_TOKEN пуст)"
DIAGNOSTICS_SEND_PAY_OK = "💳 Send Pay: ✅ авторизован"


def admin_diagnostics_send_pay_error(error: str) -> str:
    return f"💳 Send Pay: ❌ ошибка\n{error}"


def admin_diagnostics_screen(
    db_section: str, check_bot_section: str, send_pay_section: str, provider_counts: dict[str, int]
) -> str:
    network_lines = [
        f"{PROVIDER_TITLES.get(provider, provider)}: {provider_counts.get(provider, 0)} бот(ов)"
        for provider in ("flyer", "tgrass", "piarflow", "subgram")
    ]
    return (
        "🩺 Диагностика платформы\n\n"
        f"{db_section}\n\n"
        f"{check_bot_section}\n\n"
        f"{send_pay_section}\n\n"
        "Подключённые сети (по всем ботам платформы):\n" + "\n".join(network_lines)
    )


def integrations_check_none(bot: ManagedBot) -> str:
    return f"🩺 Проверка интеграций — @{bot.username}\n\nНет подключённых интеграций для проверки."


def integrations_check_screen(bot: ManagedBot, lines: list[str]) -> str:
    return f"🩺 Проверка интеграций — @{bot.username}\n\n" + "\n".join(lines)


def integrations_check_ok(provider_title: str) -> str:
    return f"✅ {provider_title} — работает"


def integrations_check_error(provider_title: str, error: str) -> str:
    return f"❌ {provider_title} — ошибка\n{error}"


INTEGRATIONS_CHECK_SUBGRAM = "⚪ Subgram — нет проверки (по этой сети нет документации API)"


def admin_category_detail(category: Category) -> str:
    return f"🏷 {category.title}"
