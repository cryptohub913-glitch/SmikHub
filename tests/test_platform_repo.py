from decimal import Decimal

import pytest

from smikhub.db import order_repo, platform_repo, repo
from smikhub.db.models import DepositStatus, WithdrawalStatus
from tests.conftest import TEST_ADMIN_ID, TEST_OWNER_ID


@pytest.mark.asyncio
async def test_platform_settings_defaults_and_toggle(session):
    settings = await platform_repo.get_platform_settings(session)

    assert settings.sell_ap_enabled is True
    assert settings.buy_ap_enabled is True

    await platform_repo.toggle_sell_ap_enabled(session, settings)
    assert settings.sell_ap_enabled is False

    await platform_repo.set_platform_field(session, settings, "min_deposit_amount", Decimal("5"))
    assert Decimal(str(settings.min_deposit_amount)) == Decimal("5")


@pytest.mark.asyncio
async def test_set_platform_field_rejects_unknown_field(session):
    settings = await platform_repo.get_platform_settings(session)

    with pytest.raises(ValueError):
        await platform_repo.set_platform_field(session, settings, "not_a_real_field", Decimal("1"))


@pytest.mark.asyncio
async def test_deposit_invoice_mark_paid_credits_balance_once(session):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    invoice = await platform_repo.create_deposit_invoice(session, user.id, "inv-x", Decimal("7.5"))

    first = await platform_repo.mark_deposit_paid(session, invoice)
    second = await platform_repo.mark_deposit_paid(session, invoice)

    assert first is True
    assert second is False  # already paid, no double credit
    assert invoice.status == DepositStatus.PAID
    assert Decimal(str(user.balance)) == Decimal("7.5")


@pytest.mark.asyncio
async def test_create_withdrawal_request_reserves_balance(session):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, Decimal("20"))

    request = await platform_repo.create_withdrawal_request(session, user, Decimal("8"))

    assert Decimal(str(user.balance)) == Decimal("12")
    assert request.status == WithdrawalStatus.PENDING
    assert request.spend_id == f"withdrawal-{request.id}"


@pytest.mark.asyncio
async def test_reject_withdrawal_refunds_balance(session):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, Decimal("20"))
    request = await platform_repo.create_withdrawal_request(session, user, Decimal("8"))

    await platform_repo.reject_withdrawal(session, request, TEST_ADMIN_ID)

    assert request.status == WithdrawalStatus.REJECTED
    assert request.decided_by == TEST_ADMIN_ID
    assert Decimal(str(user.balance)) == Decimal("20")  # refunded


@pytest.mark.asyncio
async def test_approve_withdrawal_does_not_touch_balance_again(session):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, Decimal("20"))
    request = await platform_repo.create_withdrawal_request(session, user, Decimal("8"))

    await platform_repo.approve_withdrawal(session, request, TEST_ADMIN_ID)

    assert request.status == WithdrawalStatus.APPROVED
    # Balance was already reserved at request time; approval must not deduct it again.
    assert Decimal(str(user.balance)) == Decimal("12")


@pytest.mark.asyncio
async def test_list_pending_withdrawals_excludes_decided(session):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, Decimal("100"))
    pending = await platform_repo.create_withdrawal_request(session, user, Decimal("5"))
    decided = await platform_repo.create_withdrawal_request(session, user, Decimal("5"))
    await platform_repo.approve_withdrawal(session, decided, TEST_ADMIN_ID)

    pending_list = await platform_repo.list_pending_withdrawals(session)

    assert [r.id for r in pending_list] == [pending.id]


@pytest.mark.asyncio
async def test_toggle_ban(session):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    assert user.is_banned is False

    await platform_repo.toggle_ban(session, user)
    assert user.is_banned is True

    await platform_repo.toggle_ban(session, user)
    assert user.is_banned is False


@pytest.mark.asyncio
async def test_adjust_balance_allows_negative_delta(session):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, Decimal("10"))

    await platform_repo.adjust_balance(session, user, Decimal("-3"))

    assert Decimal(str(user.balance)) == Decimal("7")


@pytest.mark.asyncio
async def test_platform_stats_aggregates(session):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, Decimal("50"))
    await repo.create_bot(
        session,
        owner_id=TEST_OWNER_ID,
        telegram_bot_id=1,
        username="bot1",
        bot_token="123:AAA",
        default_min_price=Decimal("0.0"),
        default_max_sponsors=3,
    )

    stats = await platform_repo.platform_stats(session)

    assert stats["users_count"] == 1
    assert stats["bots_count"] == 1


@pytest.mark.asyncio
async def test_user_profile_stats_returns_none_for_missing_user(session):
    assert await platform_repo.user_profile_stats(session, 424242) is None
