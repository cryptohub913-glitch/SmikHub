from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from smikhub.db import order_repo, repo
from smikhub.db.models import (
    AgeGroup,
    CategoryMode,
    DestinationType,
    Gender,
    OrderStatus,
    PremiumFilter,
    TrafficType,
)
from tests.conftest import TEST_OWNER_ID

DEFAULT_TEST_ORDER_PRICE = Decimal("1.2")


async def _make_order(session, **overrides):
    await repo.get_or_create_user(session, TEST_OWNER_ID)
    defaults = dict(
        owner_id=TEST_OWNER_ID,
        traffic_type=TrafficType.SUBSCRIPTIONS,
        destination_type=DestinationType.CHANNEL_CHAT,
        destination_link="https://t.me/example_channel",
        default_price=DEFAULT_TEST_ORDER_PRICE,
    )
    defaults.update(overrides)
    return await order_repo.create_order(session, **defaults)


@pytest.mark.asyncio
async def test_create_order_has_expected_defaults(session):
    order = await _make_order(session)

    assert order.status == OrderStatus.PAUSED
    assert Decimal(str(order.price)) == DEFAULT_TEST_ORDER_PRICE
    assert Decimal(str(order.spent)) == Decimal("0")
    assert order.gender == Gender.ANY
    assert order.age_group == AgeGroup.ANY
    assert order.premium_filter == PremiumFilter.NOT_IMPORTANT
    assert order.excluded_categories == []
    assert order.excluded_languages == []
    assert order.excluded_countries == []


@pytest.mark.asyncio
async def test_top_up_balance_accumulates(session):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)

    await order_repo.top_up_balance(session, user, Decimal("5"))
    await order_repo.top_up_balance(session, user, Decimal("2.5"))

    assert Decimal(str(user.balance)) == Decimal("7.5")


@pytest.mark.asyncio
async def test_record_join_event_rejected_while_paused(session):
    order = await _make_order(session)

    accepted = await order_repo.record_join_event(session, order, telegram_user_id=1)

    assert accepted is False
    stats = await order_repo.order_stats(session, order)
    assert stats["total"] == 0


@pytest.mark.asyncio
async def test_record_join_event_charges_balance_when_running(session):
    order = await _make_order(session)
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, Decimal("10"))
    await order_repo.toggle_status(session, order)  # -> RUNNING
    await order_repo.set_price(session, order, Decimal("2.00"))

    accepted = await order_repo.record_join_event(session, order, telegram_user_id=1)

    assert accepted is True
    assert Decimal(str(user.balance)) == Decimal("8.00")
    assert Decimal(str(order.spent)) == Decimal("2.00")
    stats = await order_repo.order_stats(session, order)
    assert stats["total"] == 1


@pytest.mark.asyncio
async def test_record_join_event_pauses_order_on_insufficient_balance(session):
    order = await _make_order(session)
    await order_repo.toggle_status(session, order)  # -> RUNNING, balance stays 0

    accepted = await order_repo.record_join_event(session, order, telegram_user_id=1)

    assert accepted is False
    assert order.status == OrderStatus.PAUSED


@pytest.mark.asyncio
async def test_record_join_event_respects_users_total_limit(session):
    order = await _make_order(session)
    await order_repo.set_users_total(session, order, 1)
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, Decimal("100"))
    await order_repo.toggle_status(session, order)

    first = await order_repo.record_join_event(session, order, telegram_user_id=1)
    second = await order_repo.record_join_event(session, order, telegram_user_id=2)

    assert first is True
    assert second is False
    assert order.status == OrderStatus.PAUSED  # total limit hit -> whole order stops


@pytest.mark.asyncio
async def test_record_join_event_respects_daily_limit_without_pausing(session):
    order = await _make_order(session)
    await order_repo.set_users_per_day(session, order, 1)
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, Decimal("100"))
    await order_repo.toggle_status(session, order)

    first = await order_repo.record_join_event(session, order, telegram_user_id=1)
    second = await order_repo.record_join_event(session, order, telegram_user_id=2)

    assert first is True
    assert second is False
    assert order.status == OrderStatus.RUNNING  # daily cap just skips, doesn't stop the order


@pytest.mark.asyncio
async def test_record_leave_event_updates_retention(session):
    order = await _make_order(session)
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, Decimal("100"))
    await order_repo.toggle_status(session, order)
    await order_repo.record_join_event(session, order, telegram_user_id=1)

    await order_repo.record_leave_event(session, order, telegram_user_id=1)

    stats = await order_repo.order_stats(session, order)
    assert stats["total"] == 1
    assert stats["retention"] == "0%"


@pytest.mark.asyncio
async def test_toggle_excluded_category_adds_and_removes(session):
    order = await _make_order(session)
    categories = await repo.list_categories(session)
    category = categories[0]

    await order_repo.toggle_excluded_category(session, order, category.id)
    assert len(order.excluded_categories) == 1

    await order_repo.toggle_excluded_category(session, order, category.id)
    assert len(order.excluded_categories) == 0


@pytest.mark.asyncio
async def test_toggle_excluded_language_and_country(session):
    order = await _make_order(session)

    await order_repo.toggle_excluded_language(session, order, "ru")
    assert {entry.code for entry in order.excluded_languages} == {"ru"}
    await order_repo.toggle_excluded_language(session, order, "ru")
    assert order.excluded_languages == []

    await order_repo.toggle_excluded_country(session, order, "us")
    assert {entry.code for entry in order.excluded_countries} == {"us"}


@pytest.mark.asyncio
async def test_delete_order_removes_it(session):
    order = await _make_order(session)
    order_id = order.id

    await order_repo.delete_order(session, order)

    assert await order_repo.get_order(session, order_id) is None


@pytest.mark.asyncio
async def test_list_user_orders_scoped_to_owner(session):
    await _make_order(session)
    await repo.get_or_create_user(session, TEST_OWNER_ID + 1)
    await order_repo.create_order(
        session,
        owner_id=TEST_OWNER_ID + 1,
        traffic_type=TrafficType.VIEWS,
        destination_type=DestinationType.RESOURCE,
        destination_link="https://example.com",
        default_price=DEFAULT_TEST_ORDER_PRICE,
    )

    orders = await order_repo.list_user_orders(session, TEST_OWNER_ID)

    assert len(orders) == 1
    assert orders[0].owner_id == TEST_OWNER_ID


@pytest.mark.asyncio
async def test_user_balance_independent_from_bot_settings(session):
    # Regression guard: balance lives on User, unrelated to ManagedBot's own settings/enums.
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    bot = await repo.create_bot(
        session,
        owner_id=TEST_OWNER_ID,
        telegram_bot_id=1,
        username="some_bot",
        bot_token="123456:AAAA",
        default_min_price=Decimal("0.0"),
        default_max_sponsors=3,
    )

    assert Decimal(str(user.balance)) == Decimal("0")
    assert bot.category_mode == CategoryMode.ALL_EXCEPT_OWN


async def _running_order_with_balance(session, balance=Decimal("100")):
    order = await _make_order(session)
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, balance)
    await order_repo.toggle_status(session, order)
    return order, user


@pytest.mark.asyncio
async def test_record_join_event_stores_price_and_username(session):
    order, _user = await _running_order_with_balance(session)
    await order_repo.set_price(session, order, Decimal("3.50"))

    await order_repo.record_join_event(session, order, telegram_user_id=42, telegram_username="ivan")

    events = await order_repo.list_recent_join_events(session, order)
    assert len(events) == 1
    assert events[0].telegram_user_id == 42
    assert events[0].telegram_username == "ivan"
    assert Decimal(str(events[0].price)) == Decimal("3.50")


@pytest.mark.asyncio
async def test_record_join_event_username_is_optional(session):
    order, _user = await _running_order_with_balance(session)

    await order_repo.record_join_event(session, order, telegram_user_id=42)

    events = await order_repo.list_recent_join_events(session, order)
    assert events[0].telegram_username is None


@pytest.mark.asyncio
async def test_list_recent_join_events_orders_newest_first_and_respects_limit(session):
    order, _user = await _running_order_with_balance(session)
    for i in range(3):
        await order_repo.record_join_event(session, order, telegram_user_id=i)

    events = await order_repo.list_recent_join_events(session, order, limit=2)

    assert len(events) == 2
    assert events[0].joined_at >= events[1].joined_at


@pytest.mark.asyncio
async def test_quality_ratio_no_events(session):
    order = await _make_order(session)

    quality, non_quality = await order_repo.quality_ratio(session, order)

    assert quality == Decimal("0.00")
    assert non_quality == Decimal("0.00")


@pytest.mark.asyncio
async def test_quality_ratio_all_retained_is_full_quality(session):
    order, _user = await _running_order_with_balance(session)
    await order_repo.record_join_event(session, order, telegram_user_id=1)
    await order_repo.record_join_event(session, order, telegram_user_id=2)

    quality, non_quality = await order_repo.quality_ratio(session, order)

    assert quality == Decimal("100.00")
    assert non_quality == Decimal("0.00")


@pytest.mark.asyncio
async def test_quality_ratio_flags_quick_leaves_as_non_quality(session):
    order, _user = await _running_order_with_balance(session)
    await order_repo.record_join_event(session, order, telegram_user_id=1)
    await order_repo.record_join_event(session, order, telegram_user_id=2)

    events = await order_repo.list_recent_join_events(session, order)
    quick_leaver = events[0]
    now = datetime.now(timezone.utc)
    quick_leaver.joined_at = now - timedelta(minutes=10)
    quick_leaver.left_at = now  # left after 10 minutes -> under the 1h threshold
    await session.commit()

    quality, non_quality = await order_repo.quality_ratio(session, order)

    assert non_quality == Decimal("50.00")
    assert quality == Decimal("50.00")


@pytest.mark.asyncio
async def test_quality_ratio_slow_leave_still_counts_as_quality(session):
    order, _user = await _running_order_with_balance(session)
    await order_repo.record_join_event(session, order, telegram_user_id=1)

    events = await order_repo.list_recent_join_events(session, order)
    event = events[0]
    now = datetime.now(timezone.utc)
    event.joined_at = now - timedelta(days=2)
    event.left_at = now  # left after 2 days -> well past the 1h threshold
    await session.commit()

    quality, non_quality = await order_repo.quality_ratio(session, order)

    assert quality == Decimal("100.00")
    assert non_quality == Decimal("0.00")


async def _verified_running_order(session, price=Decimal("2"), **overrides):
    order, _user = await _running_order_with_balance(session, Decimal("100"))
    await order_repo.set_price(session, order, price)
    await order_repo.set_target_chat(session, order, chat_id=-100123)
    for field, value in overrides.items():
        setattr(order, field, value)
    return order


@pytest.mark.asyncio
async def test_is_order_deliverable_false_when_paused(session):
    order = await _make_order(session)  # created PAUSED by default

    assert await order_repo.is_order_deliverable(session, order) is False


@pytest.mark.asyncio
async def test_is_order_deliverable_true_for_healthy_order(session):
    order = await _verified_running_order(session)

    assert await order_repo.is_order_deliverable(session, order) is True


@pytest.mark.asyncio
async def test_is_order_deliverable_false_when_total_limit_hit(session):
    order = await _verified_running_order(session, price=Decimal("1"))
    await order_repo.set_users_total(session, order, 1)
    await order_repo.record_join_event(session, order, telegram_user_id=1)

    assert await order_repo.is_order_deliverable(session, order) is False


@pytest.mark.asyncio
async def test_is_order_deliverable_false_when_daily_limit_hit(session):
    order = await _verified_running_order(session, price=Decimal("1"))
    await order_repo.set_users_per_day(session, order, 1)
    await order_repo.record_join_event(session, order, telegram_user_id=1)

    assert await order_repo.is_order_deliverable(session, order) is False


@pytest.mark.asyncio
async def test_is_order_deliverable_false_when_balance_insufficient(session):
    order = await _verified_running_order(session, price=Decimal("1000"))

    assert await order_repo.is_order_deliverable(session, order) is False


@pytest.mark.asyncio
async def test_list_eligible_orders_excludes_unverified_and_wrong_destination(session):
    verified = await _verified_running_order(session, price=Decimal("2"))
    await _make_order(session)  # paused, unverified -> excluded

    unverified_running, _user = await _running_order_with_balance(session, Decimal("100"))
    # No set_target_chat() call -> target_chat_id stays None -> excluded

    bot_destination_order, _user2 = await _running_order_with_balance(session, Decimal("100"))
    await order_repo.set_target_chat(session, bot_destination_order, chat_id=-100999)
    bot_destination_order.destination_type = DestinationType.BOT

    results = await order_repo.list_eligible_orders_for_delivery(session, is_premium=False, lang="ru", limit=10)

    assert [o.id for o in results] == [verified.id]


@pytest.mark.asyncio
async def test_list_eligible_orders_respects_premium_filter(session):
    order = await _verified_running_order(session, price=Decimal("2"))
    await order_repo.set_premium_filter(session, order, PremiumFilter.ONLY_PREMIUM)

    without_premium = await order_repo.list_eligible_orders_for_delivery(
        session, is_premium=False, lang="ru", limit=10
    )
    with_premium = await order_repo.list_eligible_orders_for_delivery(
        session, is_premium=True, lang="ru", limit=10
    )

    assert without_premium == []
    assert [o.id for o in with_premium] == [order.id]


@pytest.mark.asyncio
async def test_list_eligible_orders_respects_excluded_language(session):
    order = await _verified_running_order(session, price=Decimal("2"))
    await order_repo.toggle_excluded_language(session, order, "en")

    en_results = await order_repo.list_eligible_orders_for_delivery(session, is_premium=False, lang="en", limit=10)
    ru_results = await order_repo.list_eligible_orders_for_delivery(session, is_premium=False, lang="ru", limit=10)

    assert en_results == []
    assert [o.id for o in ru_results] == [order.id]


@pytest.mark.asyncio
async def test_list_eligible_orders_sorted_by_price_descending(session):
    cheap = await _verified_running_order(session, price=Decimal("1"))
    expensive = await _verified_running_order(session, price=Decimal("5"))

    results = await order_repo.list_eligible_orders_for_delivery(session, is_premium=False, lang="ru", limit=10)

    assert [o.id for o in results] == [expensive.id, cheap.id]


@pytest.mark.asyncio
async def test_list_eligible_orders_respects_limit(session):
    for price in (1, 2, 3):
        await _verified_running_order(session, price=Decimal(price))

    results = await order_repo.list_eligible_orders_for_delivery(session, is_premium=False, lang="ru", limit=2)

    assert len(results) == 2


@pytest.mark.asyncio
async def test_list_eligible_orders_respects_gender_filter(session):
    order = await _verified_running_order(session)
    await order_repo.set_gender(session, order, Gender.FEMALE)

    wrong_gender = await order_repo.list_eligible_orders_for_delivery(
        session, is_premium=False, lang="ru", limit=10, gender=Gender.MALE
    )
    right_gender = await order_repo.list_eligible_orders_for_delivery(
        session, is_premium=False, lang="ru", limit=10, gender=Gender.FEMALE
    )
    no_gender_data = await order_repo.list_eligible_orders_for_delivery(
        session, is_premium=False, lang="ru", limit=10, gender=None
    )

    assert wrong_gender == []
    assert [o.id for o in right_gender] == [order.id]
    # Без реальных данных о поле пользователя фильтр просто не применяется.
    assert [o.id for o in no_gender_data] == [order.id]


@pytest.mark.asyncio
async def test_list_eligible_orders_gender_any_matches_everyone(session):
    order = await _verified_running_order(session)  # gender остаётся ANY по умолчанию

    results = await order_repo.list_eligible_orders_for_delivery(
        session, is_premium=False, lang="ru", limit=10, gender=Gender.MALE
    )

    assert [o.id for o in results] == [order.id]


@pytest.mark.asyncio
async def test_list_eligible_orders_respects_age_group_filter(session):
    order = await _verified_running_order(session)
    await order_repo.set_age_group(session, order, AgeGroup.ADULT)

    wrong_age = await order_repo.list_eligible_orders_for_delivery(
        session, is_premium=False, lang="ru", limit=10, age_group=AgeGroup.AGE_14_17
    )
    right_age = await order_repo.list_eligible_orders_for_delivery(
        session, is_premium=False, lang="ru", limit=10, age_group=AgeGroup.ADULT
    )

    assert wrong_age == []
    assert [o.id for o in right_age] == [order.id]


@pytest.mark.asyncio
async def test_list_eligible_orders_respects_excluded_country(session):
    order = await _verified_running_order(session)
    await order_repo.toggle_excluded_country(session, order, "us")

    from_excluded_country = await order_repo.list_eligible_orders_for_delivery(
        session, is_premium=False, lang="ru", limit=10, country="us"
    )
    from_other_country = await order_repo.list_eligible_orders_for_delivery(
        session, is_premium=False, lang="ru", limit=10, country="ru"
    )

    assert from_excluded_country == []
    assert [o.id for o in from_other_country] == [order.id]
