from decimal import Decimal

# Фиксированный список тематик спонсоров, в порядке из спецификации.
CATEGORIES: list[tuple[str, str]] = [
    ("other", "Другое"),
    ("casino", "Казино"),
    ("crypto", "Крипта"),
    ("adult", "18+"),
    ("trash_war", "Треш/Война"),
    ("scam_giveaway", "Скам/Розыгрыши"),
    ("dating", "Общение"),
    ("vpn", "VPN"),
    ("external_links", "Внешние ссылки"),
    ("articles", "Статьи"),
    ("folders", "Папки"),
]
CATEGORY_TITLES: dict[str, str] = dict(CATEGORIES)

# Нативная площадка платформы всегда присутствует в приоритете первой по умолчанию.
NATIVE_PROVIDER = "botohub"
NATIVE_PROVIDER_TITLE = "BotoHub"

PROVIDER_TITLES: dict[str, str] = {
    NATIVE_PROVIDER: NATIVE_PROVIDER_TITLE,
    "subgram": "Subgram",
    "flyer": "Flyer",
    "tgrass": "Tgrass",
    "piarflow": "PiarFlow",
}

# Провайдеры спонсоров, для которых реализованы реальные HTTP-клиенты
# (smikhub/services/sponsor_providers/) и выдача через /api/v1/bot/sponsors.
# Subgram сюда не входит — по нему не было документации API, только хранение токена.
INTEGRATED_SPONSOR_PROVIDERS = ("flyer", "tgrass", "piarflow")

# Шаг сеток цены. Границы самих сеток (и значения по умолчанию для новых ботов/заказов)
# теперь настраиваются админом через PlatformSettings (smikhub/db/models.py) — см.
# smikhub.db.platform_repo.EDITABLE_NUMERIC_FIELDS.
PRICE_STEP = Decimal("0.1")
ORDER_PRICE_STEP = Decimal("0.1")


def price_range(min_value: Decimal, max_value: Decimal, step: Decimal) -> list[Decimal]:
    values = []
    value = min_value
    while value <= max_value:
        values.append(value.quantize(step))
        value += step
    return values


# Языки интерфейса Telegram для таргетинга заказов. Проценты аудитории на скриншотах
# конкурента — это их накопленная статистика по реальным пользователям, которой у
# платформы пока нет, поэтому список идёт без процентов.
LANGUAGES: list[tuple[str, str]] = [
    ("ru", "Русский"),
    ("uz", "Узбекский"),
    ("kk", "Казахский"),
    ("uk", "Украинский"),
    ("be", "Белорусский"),
    ("en", "Английский"),
    ("fa", "Персидский"),
    ("ar", "Арабский"),
    ("tr", "Турецкий"),
    ("de", "Немецкий"),
    ("ro", "Румынский"),
    ("fr", "Французский"),
    ("es", "Испанский"),
    ("pl", "Польский"),
    ("tg", "Таджикский"),
    ("other", "Другое"),
]
LANGUAGE_TITLES: dict[str, str] = dict(LANGUAGES)

COUNTRIES: list[tuple[str, str]] = [
    ("ru", "Россия"),
    ("de", "Германия"),
    ("ua", "Украина"),
    ("nl", "Нидерланды"),
    ("us", "США"),
    ("cz", "Чехия"),
    ("kz", "Казахстан"),
    ("by", "Беларусь"),
    ("gb", "Великобритания"),
    ("fr", "Франция"),
    ("fi", "Финляндия"),
    ("no", "Норвегия"),
    ("bg", "Болгария"),
    ("md", "Молдова"),
    ("pl", "Польша"),
    ("tm", "Туркменистан"),
    ("kg", "Киргизия"),
    ("uz", "Узбекистан"),
    ("tj", "Таджикистан"),
    ("other", "Другое"),
]
COUNTRY_TITLES: dict[str, str] = dict(COUNTRIES)
