from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from smikhub.db.models import (
    AgeGroup,
    DestinationType,
    Gender,
    Order,
    OrderExcludedCategory,
    OrderExcludedCountry,
    OrderExcludedLanguage,
    OrderJoinEvent,
    OrderStatus,
    PremiumFilter,
    TrafficType,
    User,
)


# Наша собственная эвристика отсева накруток (не сторонний антифрод-сервис): если
# пользователь вышел из чата быстрее этого порога после вступления, событие считается
# "некачественным" при подсчёте quality_ratio.
QUICK_LEAVE_THRESHOLD = timedelta(hours=1)


def _order_query():
    return select(Order).options(
        selectinload(Order.excluded_categories).selectinload(OrderExcludedCategory.category),
        selectinload(Order.excluded_languages),
        selectinload(Order.excluded_countries),
    )


async def list_user_orders(session: AsyncSession, owner_id: int) -> list[Order]:
    result = await session.execute(_order_query().where(Order.owner_id == owner_id))
    return list(result.scalars().unique())


async def get_order(session: AsyncSession, order_id: int, owner_id: int | None = None) -> Order | None:
    query = _order_query().where(Order.id == order_id)
    if owner_id is not None:
        query = query.where(Order.owner_id == owner_id)
    result = await session.execute(query)
    return result.scalars().unique().one_or_none()


async def get_running_orders_for_chat(session: AsyncSession, chat_id: int) -> list[Order]:
    result = await session.execute(
        select(Order).where(Order.target_chat_id == chat_id, Order.status == OrderStatus.RUNNING)
    )
    return list(result.scalars())


async def create_order(
    session: AsyncSession,
    owner_id: int,
    traffic_type: TrafficType,
    destination_type: DestinationType,
    destination_link: str,
    default_price: Decimal,
) -> Order:
    order = Order(
        owner_id=owner_id,
        traffic_type=traffic_type,
        destination_type=destination_type,
        destination_link=destination_link,
        price=default_price,
        excluded_categories=[],
        excluded_languages=[],
        excluded_countries=[],
        join_events=[],
    )
    session.add(order)
    await session.commit()
    return order


async def delete_order(session: AsyncSession, order: Order) -> None:
    await session.delete(order)
    await session.commit()


async def toggle_status(session: AsyncSession, order: Order) -> None:
    order.status = OrderStatus.RUNNING if order.status == OrderStatus.PAUSED else OrderStatus.PAUSED
    await session.commit()


async def set_price(session: AsyncSession, order: Order, price: Decimal) -> None:
    order.price = price
    await session.commit()


async def set_destination_link(session: AsyncSession, order: Order, link: str) -> None:
    order.destination_link = link
    order.target_chat_id = None
    await session.commit()


async def set_target_chat(session: AsyncSession, order: Order, chat_id: int) -> None:
    order.target_chat_id = chat_id
    await session.commit()


async def set_users_per_day(session: AsyncSession, order: Order, value: int | None) -> None:
    order.users_per_day = value
    await session.commit()


async def set_users_total(session: AsyncSession, order: Order, value: int | None) -> None:
    order.users_total = value
    await session.commit()


async def toggle_distribute_during_day(session: AsyncSession, order: Order) -> None:
    order.distribute_during_day = not order.distribute_during_day
    await session.commit()


async def set_gender(session: AsyncSession, order: Order, gender: Gender) -> None:
    order.gender = gender
    await session.commit()


async def set_age_group(session: AsyncSession, order: Order, age_group: AgeGroup) -> None:
    order.age_group = age_group
    await session.commit()


async def set_premium_filter(session: AsyncSession, order: Order, value: PremiumFilter) -> None:
    order.premium_filter = value
    await session.commit()


async def toggle_excluded_category(session: AsyncSession, order: Order, category_id: int) -> None:
    existing = next((c for c in order.excluded_categories if c.category_id == category_id), None)
    if existing is not None:
        order.excluded_categories.remove(existing)
    else:
        order.excluded_categories.append(OrderExcludedCategory(category_id=category_id))
    await session.commit()


async def toggle_excluded_language(session: AsyncSession, order: Order, code: str) -> None:
    existing = next((entry for entry in order.excluded_languages if entry.code == code), None)
    if existing is not None:
        order.excluded_languages.remove(existing)
    else:
        order.excluded_languages.append(OrderExcludedLanguage(code=code))
    await session.commit()


async def toggle_excluded_country(session: AsyncSession, order: Order, code: str) -> None:
    existing = next((entry for entry in order.excluded_countries if entry.code == code), None)
    if existing is not None:
        order.excluded_countries.remove(existing)
    else:
        order.excluded_countries.append(OrderExcludedCountry(code=code))
    await session.commit()


async def top_up_balance(session: AsyncSession, user: User, amount: Decimal) -> None:
    user.balance = Decimal(str(user.balance)) + amount
    await session.commit()


async def order_stats(session: AsyncSession, order: Order) -> dict[str, object]:
    total = (
        await session.execute(
            select(func.count()).select_from(OrderJoinEvent).where(OrderJoinEvent.order_id == order.id)
        )
    ).scalar_one()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today = (
        await session.execute(
            select(func.count())
            .select_from(OrderJoinEvent)
            .where(OrderJoinEvent.order_id == order.id, OrderJoinEvent.joined_at >= today_start)
        )
    ).scalar_one()

    retained = (
        await session.execute(
            select(func.count())
            .select_from(OrderJoinEvent)
            .where(OrderJoinEvent.order_id == order.id, OrderJoinEvent.left_at.is_(None))
        )
    ).scalar_one()

    retention = f"{retained / total * 100:.0f}%" if total else "—"
    return {"total": total, "today": today, "retention": retention}


async def _order_join_count(session: AsyncSession, order_id: int, since: datetime | None = None) -> int:
    query = select(func.count()).select_from(OrderJoinEvent).where(OrderJoinEvent.order_id == order_id)
    if since is not None:
        query = query.where(OrderJoinEvent.joined_at >= since)
    return (await session.execute(query)).scalar_one()


def _today_start() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


async def is_order_deliverable(session: AsyncSession, order: Order) -> bool:
    """Можно ли прямо сейчас предлагать заказ к показу: активен, не упёрся в лимиты, у
    владельца хватает баланса на одну оплату. Используется при формировании выдачи
    /api/v1/bot/sponsors — чтобы не показывать заведомо неликвидные заказы. Итоговое
    решение о списании всё равно принимает record_join_event (состояние могло измениться
    между показом и реальным вступлением)."""
    if order.status != OrderStatus.RUNNING:
        return False
    if order.users_total is not None and await _order_join_count(session, order.id) >= order.users_total:
        return False
    if order.users_per_day is not None:
        today_count = await _order_join_count(session, order.id, since=_today_start())
        if today_count >= order.users_per_day:
            return False
    owner = await session.get(User, order.owner_id)
    if Decimal(str(owner.balance)) < Decimal(str(order.price)):
        return False
    return True


async def list_eligible_orders_for_delivery(
    session: AsyncSession,
    is_premium: bool,
    lang: str | None,
    limit: int,
    gender: Gender | None = None,
    age_group: AgeGroup | None = None,
    country: str | None = None,
) -> list[Order]:
    """Заказы "Купить ОП", которые прямо сейчас реально можно предложить боту-издателю.

    Ограничено CHANNEL_CHAT с подтверждённым target_chat_id — это единственный тип
    назначения, где у нас есть реальное подтверждение конверсии через check-бота (см.
    docs/api-integration.md). Заказы "Бот"/"Ресурс" сюда не попадают.

    gender/age_group/country — необязательные реальные данные о пользователе (сейчас
    единственный источник — профиль подписчика Tgrass, см.
    smikhub/api/routers/sponsors.py). Когда их нет (None), соответствующий фильтр заказа
    просто не проверяется — так же, как и раньше.
    """
    if limit <= 0:
        return []

    query = (
        select(Order)
        .where(
            Order.status == OrderStatus.RUNNING,
            Order.destination_type == DestinationType.CHANNEL_CHAT,
            Order.target_chat_id.is_not(None),
        )
        .order_by(Order.price.desc(), Order.created_at.asc())
        .options(selectinload(Order.excluded_languages), selectinload(Order.excluded_countries))
        # Берём с запасом: часть кандидатов ниже отсеется по premium/языку/лимитам/балансу.
        .limit(limit * 3)
    )
    candidates = list((await session.execute(query)).scalars().unique())

    eligible: list[Order] = []
    for order in candidates:
        if order.premium_filter == PremiumFilter.ONLY_PREMIUM and not is_premium:
            continue
        if lang and any(entry.code == lang for entry in order.excluded_languages):
            continue
        if gender is not None and order.gender != Gender.ANY and order.gender != gender:
            continue
        if age_group is not None and order.age_group != AgeGroup.ANY and order.age_group != age_group:
            continue
        if country and any(entry.code == country for entry in order.excluded_countries):
            continue
        if not await is_order_deliverable(session, order):
            continue
        eligible.append(order)
        if len(eligible) >= limit:
            break
    return eligible


async def record_join_event(
    session: AsyncSession, order: Order, telegram_user_id: int, telegram_username: str | None = None
) -> bool:
    """Проверяет лимиты/баланс и, если можно, списывает цену и фиксирует событие.

    Возвращает True, если вступление принято и оплачено, иначе False (заказ на паузе,
    исчерпан лимит или не хватает баланса — в последнем случае заказ автоматически
    ставится на паузу).
    """
    if order.status != OrderStatus.RUNNING:
        return False

    if order.users_total is not None and await _order_join_count(session, order.id) >= order.users_total:
        order.status = OrderStatus.PAUSED
        await session.commit()
        return False

    if order.users_per_day is not None:
        today_count = await _order_join_count(session, order.id, since=_today_start())
        if today_count >= order.users_per_day:
            return False

    owner = await session.get(User, order.owner_id)
    price = Decimal(str(order.price))
    if Decimal(str(owner.balance)) < price:
        order.status = OrderStatus.PAUSED
        await session.commit()
        return False

    owner.balance = Decimal(str(owner.balance)) - price
    order.spent = Decimal(str(order.spent)) + price
    session.add(
        OrderJoinEvent(
            order_id=order.id,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            price=price,
        )
    )
    await session.commit()
    return True


async def record_leave_event(session: AsyncSession, order: Order, telegram_user_id: int) -> None:
    result = await session.execute(
        select(OrderJoinEvent)
        .where(
            OrderJoinEvent.order_id == order.id,
            OrderJoinEvent.telegram_user_id == telegram_user_id,
            OrderJoinEvent.left_at.is_(None),
        )
        .order_by(OrderJoinEvent.joined_at.desc())
    )
    event = result.scalars().first()
    if event is not None:
        event.left_at = datetime.now(timezone.utc)
        await session.commit()


async def list_recent_join_events(session: AsyncSession, order: Order, limit: int = 10) -> list[OrderJoinEvent]:
    result = await session.execute(
        select(OrderJoinEvent)
        .where(OrderJoinEvent.order_id == order.id)
        .order_by(OrderJoinEvent.joined_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def quality_ratio(session: AsyncSession, order: Order) -> tuple[Decimal, Decimal]:
    """Доля "качественных"/"некачественных" вступлений по нашей эвристике: событие
    считается некачественным, если пользователь вышел быстрее QUICK_LEAVE_THRESHOLD после
    вступления. Возвращает (quality_pct, non_quality_pct), обе Decimal с 2 знаками.

    Сравнение порога делается в Python, а не в SQL — вычитание дат не переносится
    одинаково между бэкендами (в частности, SQLite хранит даты как текст).
    """
    result = await session.execute(
        select(OrderJoinEvent.joined_at, OrderJoinEvent.left_at).where(OrderJoinEvent.order_id == order.id)
    )
    rows = result.all()
    total = len(rows)
    if total == 0:
        return Decimal("0.00"), Decimal("0.00")

    non_quality = sum(
        1 for joined_at, left_at in rows if left_at is not None and (left_at - joined_at) < QUICK_LEAVE_THRESHOLD
    )

    non_quality_pct = (Decimal(non_quality) / Decimal(total) * 100).quantize(Decimal("0.01"))
    quality_pct = (Decimal("100.00") - non_quality_pct).quantize(Decimal("0.01"))
    return quality_pct, non_quality_pct
