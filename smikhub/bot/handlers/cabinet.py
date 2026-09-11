from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import CabinetCB, DepositCheckCB, MenuCB
from smikhub.bot.keyboards import admin_withdrawal_detail_kb, cabinet_cancel_kb, cabinet_kb, deposit_invoice_kb
from smikhub.bot.states import CabinetStates
from smikhub.config import get_settings
from smikhub.db import platform_repo, repo
from smikhub.db.models import DepositInvoice, DepositStatus, WithdrawalRequest
from smikhub.services import send_pay
from smikhub.services.send_pay import SendPayError

router = Router(name="cabinet")


def _parse_positive_decimal(text: str) -> Decimal | None:
    try:
        value = Decimal(text.strip().replace(",", "."))
    except InvalidOperation:
        return None
    return value if value > 0 else None


@router.callback_query(MenuCB.filter(F.target == "cabinet"))
async def show_cabinet(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    user = await repo.get_or_create_user(session, callback.from_user.id)
    await callback.message.edit_text(texts.cabinet_screen(user), reply_markup=cabinet_kb())
    await callback.answer()


@router.callback_query(CabinetCB.filter(F.action == "cancel"))
async def cancel_cabinet_input(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    user = await repo.get_or_create_user(session, callback.from_user.id)
    await callback.message.edit_text(texts.cabinet_screen(user), reply_markup=cabinet_kb())
    await callback.answer()


@router.callback_query(CabinetCB.filter(F.action == "deposit"))
async def request_deposit_amount(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not get_settings().send_api_token:
        await callback.answer(texts.DEPOSIT_SERVICE_UNAVAILABLE, show_alert=True)
        return

    platform_settings = await platform_repo.get_platform_settings(session)
    await state.set_state(CabinetStates.waiting_for_deposit_amount)
    await callback.message.edit_text(
        texts.deposit_amount_prompt(platform_settings.min_deposit_amount), reply_markup=cabinet_cancel_kb()
    )
    await callback.answer()


@router.message(CabinetStates.waiting_for_deposit_amount)
async def receive_deposit_amount(message: Message, session: AsyncSession, state: FSMContext) -> None:
    amount = _parse_positive_decimal(message.text or "")
    if amount is None:
        await message.answer(texts.DEPOSIT_INVALID_AMOUNT, reply_markup=cabinet_cancel_kb())
        return

    platform_settings = await platform_repo.get_platform_settings(session)
    min_amount = Decimal(str(platform_settings.min_deposit_amount))
    if amount < min_amount:
        await message.answer(texts.deposit_amount_too_small(min_amount), reply_markup=cabinet_cancel_kb())
        return

    user = await repo.get_or_create_user(session, message.from_user.id)
    try:
        result = await send_pay.create_invoice(amount, payload=str(user.id))
    except SendPayError:
        await message.answer(texts.DEPOSIT_CREATE_FAILED, reply_markup=cabinet_cancel_kb())
        return

    invoice = await platform_repo.create_deposit_invoice(
        session, user_id=user.id, send_invoice_id=str(result["invoice_id"]), amount=amount
    )
    await state.clear()
    await message.answer(
        texts.deposit_invoice_created(amount),
        reply_markup=deposit_invoice_kb(invoice.id, result["pay_url"]),
    )


@router.callback_query(DepositCheckCB.filter())
async def check_deposit_payment(
    callback: CallbackQuery, callback_data: DepositCheckCB, session: AsyncSession
) -> None:
    invoice = await session.get(DepositInvoice, callback_data.invoice_id)
    if invoice is None or invoice.user_id != callback.from_user.id:
        await callback.answer("Счёт не найден", show_alert=True)
        return

    if invoice.status == DepositStatus.PAID:
        await callback.answer(texts.DEPOSIT_ALREADY_CREDITED, show_alert=True)
        return

    try:
        items = await send_pay.get_invoices([invoice.send_invoice_id])
    except SendPayError:
        await callback.answer(texts.DEPOSIT_STILL_PENDING, show_alert=True)
        return

    remote = next(
        (item for item in items if str(item.get("invoice_id")) == invoice.send_invoice_id), None
    )
    if remote is None or remote.get("status") != "paid":
        await callback.answer(texts.DEPOSIT_STILL_PENDING, show_alert=True)
        return

    await platform_repo.mark_deposit_paid(session, invoice)
    user = await repo.get_or_create_user(session, callback.from_user.id)
    await callback.message.edit_text(texts.cabinet_screen(user), reply_markup=cabinet_kb())
    await callback.answer("✅ Зачислено!")


@router.callback_query(CabinetCB.filter(F.action == "withdraw"))
async def request_withdrawal_amount(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not get_settings().send_api_token:
        await callback.answer(texts.WITHDRAWAL_SERVICE_UNAVAILABLE, show_alert=True)
        return

    user = await repo.get_or_create_user(session, callback.from_user.id)
    platform_settings = await platform_repo.get_platform_settings(session)
    await state.set_state(CabinetStates.waiting_for_withdrawal_amount)
    await callback.message.edit_text(
        texts.withdrawal_amount_prompt(user.balance, platform_settings.min_withdrawal_amount),
        reply_markup=cabinet_cancel_kb(),
    )
    await callback.answer()


@router.message(CabinetStates.waiting_for_withdrawal_amount)
async def receive_withdrawal_amount(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await repo.get_or_create_user(session, message.from_user.id)
    platform_settings = await platform_repo.get_platform_settings(session)
    min_amount = Decimal(str(platform_settings.min_withdrawal_amount))
    balance = Decimal(str(user.balance))

    amount = _parse_positive_decimal(message.text or "")
    if amount is None or amount < min_amount or amount > balance:
        await message.answer(
            texts.withdrawal_amount_invalid(balance, min_amount), reply_markup=cabinet_cancel_kb()
        )
        return

    request = await platform_repo.create_withdrawal_request(session, user, amount)
    await state.clear()
    await message.answer(texts.WITHDRAWAL_REQUEST_CREATED, reply_markup=cabinet_kb())
    await _notify_admins(message, request, user.id, amount)


async def _notify_admins(message: Message, request: WithdrawalRequest, user_id: int, amount: Decimal) -> None:
    text = texts.withdrawal_admin_notification(request.id, user_id, amount)
    for admin_id in get_settings().admin_ids:
        try:
            await message.bot.send_message(admin_id, text, reply_markup=admin_withdrawal_detail_kb(request.id))
        except TelegramAPIError:
            pass
