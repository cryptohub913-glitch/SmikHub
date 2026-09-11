from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from smikhub.bot.admin_guard import IsAdmin
from smikhub.bot.callback_data import AdminWithdrawalCB
from smikhub.bot.handlers import admin
from smikhub.db import order_repo, platform_repo, repo
from smikhub.db.models import WithdrawalStatus
from smikhub.services.send_pay import SendPayError
from tests.conftest import TEST_ADMIN_ID, TEST_OWNER_ID


def _make_callback(user_id: int) -> MagicMock:
    callback = MagicMock()
    callback.from_user = SimpleNamespace(id=user_id)
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


@pytest.mark.asyncio
async def test_is_admin_filter():
    is_admin = IsAdmin()
    admin_event = SimpleNamespace(from_user=SimpleNamespace(id=TEST_ADMIN_ID))
    stranger_event = SimpleNamespace(from_user=SimpleNamespace(id=TEST_OWNER_ID))

    assert await is_admin(admin_event) is True
    assert await is_admin(stranger_event) is False


async def _make_pending_withdrawal(session, amount=Decimal("10")):
    user = await repo.get_or_create_user(session, TEST_OWNER_ID)
    await order_repo.top_up_balance(session, user, Decimal("50"))
    return user, await platform_repo.create_withdrawal_request(session, user, amount)


@pytest.mark.asyncio
async def test_approve_withdrawal_calls_transfer_and_marks_approved(session, monkeypatch):
    user, request = await _make_pending_withdrawal(session)
    monkeypatch.setattr(admin.send_pay, "transfer", AsyncMock(return_value={"ok": True}))

    callback = _make_callback(TEST_ADMIN_ID)
    await admin.approve_withdrawal(callback, AdminWithdrawalCB(action="approve", withdrawal_id=request.id), session)

    assert request.status == WithdrawalStatus.APPROVED
    assert Decimal(str(user.balance)) == Decimal("40")  # reserved at request time, unchanged here
    admin.send_pay.transfer.assert_awaited_once_with(user.id, Decimal("10"), request.spend_id)


@pytest.mark.asyncio
async def test_approve_withdrawal_keeps_pending_on_transfer_failure(session, monkeypatch):
    user, request = await _make_pending_withdrawal(session)
    monkeypatch.setattr(admin.send_pay, "transfer", AsyncMock(side_effect=SendPayError("boom")))

    callback = _make_callback(TEST_ADMIN_ID)
    await admin.approve_withdrawal(callback, AdminWithdrawalCB(action="approve", withdrawal_id=request.id), session)

    assert request.status == WithdrawalStatus.PENDING
    callback.answer.assert_awaited_once()
    assert callback.answer.await_args.kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_reject_withdrawal_refunds_balance(session):
    user, request = await _make_pending_withdrawal(session)

    callback = _make_callback(TEST_ADMIN_ID)
    await admin.reject_withdrawal(callback, AdminWithdrawalCB(action="reject", withdrawal_id=request.id), session)

    assert request.status == WithdrawalStatus.REJECTED
    assert Decimal(str(user.balance)) == Decimal("50")


@pytest.mark.asyncio
async def test_approve_already_decided_withdrawal_is_rejected(session):
    user, request = await _make_pending_withdrawal(session)
    await platform_repo.approve_withdrawal(session, request, TEST_ADMIN_ID)

    callback = _make_callback(TEST_ADMIN_ID)
    await admin.approve_withdrawal(callback, AdminWithdrawalCB(action="approve", withdrawal_id=request.id), session)

    callback.answer.assert_awaited_once()
    assert "уже обработана" in callback.answer.await_args.args[0]
