from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.admin_guard import IsAdmin
from smikhub.bot.callback_data import (
    AdminCategoryCB,
    AdminMenuCB,
    AdminSettingsCB,
    AdminStatsCB,
    AdminUserCB,
    AdminWithdrawalCB,
)
from smikhub.bot.keyboards import (
    admin_back_kb,
    admin_categories_cancel_kb,
    admin_categories_kb,
    admin_category_delete_confirm_kb,
    admin_category_detail_kb,
    admin_menu_kb,
    admin_prices_cancel_kb,
    admin_prices_kb,
    admin_settings_kb,
    admin_stats_kb,
    admin_user_profile_kb,
    admin_users_search_kb,
    admin_withdrawal_detail_kb,
    admin_withdrawals_list_kb,
)
from smikhub.bot.states import AdminStates
from smikhub.config import get_settings
from smikhub.db import platform_repo, repo
from smikhub.db.models import Category, User, WithdrawalStatus
from smikhub.services import send_pay
from smikhub.services.send_pay import SendPayError
from smikhub.services.telegram_client import fetch_bot_identity

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _parse_decimal(text: str) -> Decimal | None:
    try:
        return Decimal(text.strip().replace(",", "."))
    except InvalidOperation:
        return None


async def _render_admin_menu(target: Message | CallbackQuery) -> None:
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(texts.ADMIN_MENU, reply_markup=admin_menu_kb())
    else:
        await target.answer(texts.ADMIN_MENU, reply_markup=admin_menu_kb())


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _render_admin_menu(message)


@router.callback_query(AdminMenuCB.filter(F.target == "main"))
async def show_admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _render_admin_menu(callback)
    await callback.answer()


# ---- Заявки на вывод ----


@router.callback_query(AdminMenuCB.filter(F.target == "withdrawals"))
async def show_withdrawals(callback: CallbackQuery, session: AsyncSession) -> None:
    requests = await platform_repo.list_pending_withdrawals(session)
    if requests:
        await callback.message.edit_text(
            texts.ADMIN_WITHDRAWALS_HEADER, reply_markup=admin_withdrawals_list_kb(requests)
        )
    else:
        await callback.message.edit_text(texts.ADMIN_WITHDRAWALS_EMPTY, reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(AdminWithdrawalCB.filter(F.action == "show"))
async def show_withdrawal_detail(
    callback: CallbackQuery, callback_data: AdminWithdrawalCB, session: AsyncSession
) -> None:
    withdrawal = await platform_repo.get_withdrawal(session, callback_data.withdrawal_id)
    if withdrawal is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    await callback.message.edit_text(
        texts.withdrawal_detail(withdrawal, withdrawal.user_id),
        reply_markup=admin_withdrawal_detail_kb(withdrawal.id),
    )
    await callback.answer()


@router.callback_query(AdminWithdrawalCB.filter(F.action == "approve"))
async def approve_withdrawal(
    callback: CallbackQuery, callback_data: AdminWithdrawalCB, session: AsyncSession
) -> None:
    withdrawal = await platform_repo.get_withdrawal(session, callback_data.withdrawal_id)
    if withdrawal is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    if withdrawal.status != WithdrawalStatus.PENDING:
        await callback.answer("Заявка уже обработана", show_alert=True)
        return

    try:
        await send_pay.transfer(withdrawal.user_id, Decimal(str(withdrawal.amount)), withdrawal.spend_id)
    except SendPayError as error:
        await callback.answer(texts.withdrawal_transfer_failed(str(error)), show_alert=True)
        return

    await platform_repo.approve_withdrawal(session, withdrawal, callback.from_user.id)
    await callback.message.edit_text(texts.WITHDRAWAL_APPROVED, reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(AdminWithdrawalCB.filter(F.action == "reject"))
async def reject_withdrawal(
    callback: CallbackQuery, callback_data: AdminWithdrawalCB, session: AsyncSession
) -> None:
    withdrawal = await platform_repo.get_withdrawal(session, callback_data.withdrawal_id)
    if withdrawal is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    if withdrawal.status != WithdrawalStatus.PENDING:
        await callback.answer("Заявка уже обработана", show_alert=True)
        return

    await platform_repo.reject_withdrawal(session, withdrawal, callback.from_user.id)
    await callback.message.edit_text(texts.WITHDRAWAL_REJECTED, reply_markup=admin_back_kb())
    await callback.answer()


# ---- Статистика ----


@router.callback_query(AdminMenuCB.filter(F.target == "stats"))
async def show_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    stats = await platform_repo.platform_stats(session)
    await callback.message.edit_text(texts.admin_stats_screen(stats), reply_markup=admin_stats_kb())
    await callback.answer()


@router.callback_query(AdminStatsCB.filter(F.target == "bots"))
async def show_bots_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    bots = await platform_repo.list_bots_admin(session)
    await callback.message.edit_text(texts.admin_bots_list_screen(bots), reply_markup=admin_back_kb())
    await callback.answer()


# ---- Диагностика ----


@router.callback_query(AdminMenuCB.filter(F.target == "diagnostics"))
async def show_diagnostics(callback: CallbackQuery, session: AsyncSession) -> None:
    app_settings = get_settings()

    try:
        stats = await platform_repo.platform_stats(session)
        db_section = texts.admin_diagnostics_db_ok(stats)
    except Exception as error:
        db_section = texts.admin_diagnostics_db_error(str(error))

    if not app_settings.check_bot_token:
        check_bot_section = texts.DIAGNOSTICS_CHECK_BOT_NOT_CONFIGURED
    else:
        identity = await fetch_bot_identity(app_settings.check_bot_token)
        check_bot_section = (
            texts.admin_diagnostics_check_bot_ok(identity.username or str(identity.id))
            if identity is not None
            else texts.DIAGNOSTICS_CHECK_BOT_ERROR
        )

    if not app_settings.send_api_token:
        send_pay_section = texts.DIAGNOSTICS_SEND_PAY_NOT_CONFIGURED
    else:
        try:
            await send_pay.check_auth()
            send_pay_section = texts.DIAGNOSTICS_SEND_PAY_OK
        except SendPayError as error:
            send_pay_section = texts.admin_diagnostics_send_pay_error(str(error))

    provider_counts = await platform_repo.count_integrations_by_provider(session)

    await callback.message.edit_text(
        texts.admin_diagnostics_screen(db_section, check_bot_section, send_pay_section, provider_counts),
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


# ---- Пользователи ----


async def _prompt_user_search(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_for_user_search)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(texts.ADMIN_USER_SEARCH_PROMPT, reply_markup=admin_users_search_kb())
    else:
        await target.answer(texts.ADMIN_USER_SEARCH_PROMPT, reply_markup=admin_users_search_kb())


@router.callback_query(AdminMenuCB.filter(F.target == "users"))
async def show_user_search(callback: CallbackQuery, state: FSMContext) -> None:
    await _prompt_user_search(callback, state)
    await callback.answer()


@router.callback_query(AdminUserCB.filter(F.action == "search_again"))
async def search_again(callback: CallbackQuery, state: FSMContext) -> None:
    await _prompt_user_search(callback, state)
    await callback.answer()


@router.message(AdminStates.waiting_for_user_search)
async def receive_user_search(message: Message, session: AsyncSession, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        await message.answer(texts.ADMIN_INVALID_ID, reply_markup=admin_users_search_kb())
        return

    stats = await platform_repo.user_profile_stats(session, int(text))
    if stats is None:
        await message.answer(texts.ADMIN_USER_NOT_FOUND, reply_markup=admin_users_search_kb())
        return

    await state.clear()
    await message.answer(texts.admin_user_profile(stats), reply_markup=admin_user_profile_kb(stats["user"]))


@router.callback_query(AdminUserCB.filter(F.action == "ban"))
async def toggle_user_ban(callback: CallbackQuery, callback_data: AdminUserCB, session: AsyncSession) -> None:
    user = await session.get(User, callback_data.user_id)
    if user is None:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    await platform_repo.toggle_ban(session, user)
    stats = await platform_repo.user_profile_stats(session, user.id)
    await callback.message.edit_text(texts.admin_user_profile(stats), reply_markup=admin_user_profile_kb(user))
    await callback.answer()


@router.callback_query(AdminUserCB.filter(F.action == "balance"))
async def request_balance_delta(
    callback: CallbackQuery, callback_data: AdminUserCB, state: FSMContext
) -> None:
    await state.set_state(AdminStates.waiting_for_balance_delta)
    await state.update_data(user_id=callback_data.user_id)
    await callback.message.edit_text(texts.ADMIN_BALANCE_DELTA_PROMPT, reply_markup=admin_back_kb())
    await callback.answer()


@router.message(AdminStates.waiting_for_balance_delta)
async def receive_balance_delta(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    user_id = data.get("user_id")
    delta = _parse_decimal(message.text or "")

    if user_id is None or delta is None or delta == 0:
        await message.answer(texts.ADMIN_BALANCE_DELTA_INVALID, reply_markup=admin_back_kb())
        return

    user = await session.get(User, user_id)
    if user is None:
        await state.clear()
        await message.answer("Пользователь не найден", reply_markup=admin_back_kb())
        return

    await platform_repo.adjust_balance(session, user, delta)
    await state.clear()
    stats = await platform_repo.user_profile_stats(session, user.id)
    await message.answer(
        f"{texts.admin_balance_adjusted(user)}\n\n{texts.admin_user_profile(stats)}",
        reply_markup=admin_user_profile_kb(user),
    )


# ---- Настройки ----


@router.callback_query(AdminMenuCB.filter(F.target == "settings"))
async def show_settings(callback: CallbackQuery, session: AsyncSession) -> None:
    await _render_settings(callback, session)
    await callback.answer()


async def _render_settings(callback: CallbackQuery, session: AsyncSession) -> None:
    settings = await platform_repo.get_platform_settings(session)
    app_settings = get_settings()
    await callback.message.edit_text(
        texts.admin_settings_screen(
            settings,
            send_configured=bool(app_settings.send_api_token),
            check_bot_configured=bool(app_settings.check_bot_token),
        ),
        reply_markup=admin_settings_kb(),
    )


@router.callback_query(AdminSettingsCB.filter(F.action == "toggle_sell"))
async def toggle_sell(callback: CallbackQuery, session: AsyncSession) -> None:
    settings = await platform_repo.get_platform_settings(session)
    await platform_repo.toggle_sell_ap_enabled(session, settings)
    await _render_settings(callback, session)
    await callback.answer()


@router.callback_query(AdminSettingsCB.filter(F.action == "toggle_buy"))
async def toggle_buy(callback: CallbackQuery, session: AsyncSession) -> None:
    settings = await platform_repo.get_platform_settings(session)
    await platform_repo.toggle_buy_ap_enabled(session, settings)
    await _render_settings(callback, session)
    await callback.answer()


# ---- Цены и лимиты ----


@router.callback_query(AdminSettingsCB.filter(F.action == "show_prices"))
async def show_prices(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    settings = await platform_repo.get_platform_settings(session)
    await callback.message.edit_text(texts.admin_prices_screen(settings), reply_markup=admin_prices_kb(settings))
    await callback.answer()


@router.callback_query(AdminSettingsCB.filter(F.action == "edit_field"))
async def request_field_value(
    callback: CallbackQuery, callback_data: AdminSettingsCB, state: FSMContext
) -> None:
    label, _kind = platform_repo.EDITABLE_NUMERIC_FIELDS[callback_data.field]
    await state.set_state(AdminStates.waiting_for_platform_field)
    await state.update_data(field=callback_data.field)
    await callback.message.edit_text(
        texts.admin_edit_field_prompt(label), reply_markup=admin_prices_cancel_kb()
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_platform_field)
async def receive_field_value(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    field = data.get("field")
    if field not in platform_repo.EDITABLE_NUMERIC_FIELDS:
        await state.clear()
        return

    _label, kind = platform_repo.EDITABLE_NUMERIC_FIELDS[field]
    raw_value = _parse_decimal(message.text or "")
    if raw_value is None or raw_value <= 0:
        await message.answer(texts.ADMIN_INVALID_AMOUNT, reply_markup=admin_prices_cancel_kb())
        return

    value: Decimal | int = int(raw_value) if kind == "int" else raw_value

    settings = await platform_repo.get_platform_settings(session)
    await platform_repo.set_platform_field(session, settings, field, value)
    await state.clear()
    await message.answer(texts.admin_prices_screen(settings), reply_markup=admin_prices_kb(settings))


# ---- Тематики ----


@router.callback_query(AdminCategoryCB.filter(F.action == "show"))
async def show_categories(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    categories = await repo.list_categories(session)
    await callback.message.edit_text(
        texts.admin_categories_screen(categories), reply_markup=admin_categories_kb(categories)
    )
    await callback.answer()


@router.callback_query(AdminCategoryCB.filter(F.action == "detail"))
async def show_category_detail(
    callback: CallbackQuery, callback_data: AdminCategoryCB, session: AsyncSession
) -> None:
    category = await session.get(Category, callback_data.category_id)
    if category is None:
        await callback.answer(texts.ADMIN_CATEGORY_NOT_FOUND, show_alert=True)
        return
    await callback.message.edit_text(
        texts.admin_category_detail(category), reply_markup=admin_category_detail_kb(category.id)
    )
    await callback.answer()


@router.callback_query(AdminCategoryCB.filter(F.action == "add"))
async def request_new_category(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_for_category_title)
    await state.update_data(category_id=None)
    await callback.message.edit_text(
        texts.ADMIN_CATEGORY_ADD_PROMPT, reply_markup=admin_categories_cancel_kb()
    )
    await callback.answer()


@router.callback_query(AdminCategoryCB.filter(F.action == "rename"))
async def request_rename_category(
    callback: CallbackQuery, callback_data: AdminCategoryCB, state: FSMContext
) -> None:
    await state.set_state(AdminStates.waiting_for_category_title)
    await state.update_data(category_id=callback_data.category_id)
    await callback.message.edit_text(
        texts.ADMIN_CATEGORY_RENAME_PROMPT, reply_markup=admin_categories_cancel_kb()
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_category_title)
async def receive_category_title(message: Message, session: AsyncSession, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer(texts.ADMIN_CATEGORY_INVALID_TITLE, reply_markup=admin_categories_cancel_kb())
        return

    data = await state.get_data()
    category_id = data.get("category_id")
    await state.clear()

    if category_id is None:
        await repo.create_category(session, title)
    else:
        category = await session.get(Category, category_id)
        if category is None:
            await message.answer(texts.ADMIN_CATEGORY_NOT_FOUND, reply_markup=admin_back_kb())
            return
        await repo.rename_category(session, category, title)

    categories = await repo.list_categories(session)
    await message.answer(texts.admin_categories_screen(categories), reply_markup=admin_categories_kb(categories))


@router.callback_query(AdminCategoryCB.filter(F.action == "delete_confirm"))
async def confirm_delete_category(
    callback: CallbackQuery, callback_data: AdminCategoryCB, session: AsyncSession
) -> None:
    category = await session.get(Category, callback_data.category_id)
    if category is None:
        await callback.answer(texts.ADMIN_CATEGORY_NOT_FOUND, show_alert=True)
        return
    await callback.message.edit_text(
        texts.ADMIN_CATEGORY_DELETE_CONFIRM, reply_markup=admin_category_delete_confirm_kb(category.id)
    )
    await callback.answer()


@router.callback_query(AdminCategoryCB.filter(F.action == "delete_cancel"))
async def cancel_delete_category(
    callback: CallbackQuery, callback_data: AdminCategoryCB, session: AsyncSession
) -> None:
    category = await session.get(Category, callback_data.category_id)
    if category is None:
        await callback.answer(texts.ADMIN_CATEGORY_NOT_FOUND, show_alert=True)
        return
    await callback.message.edit_text(
        texts.admin_category_detail(category), reply_markup=admin_category_detail_kb(category.id)
    )
    await callback.answer()


@router.callback_query(AdminCategoryCB.filter(F.action == "delete_yes"))
async def delete_category(
    callback: CallbackQuery, callback_data: AdminCategoryCB, session: AsyncSession
) -> None:
    category = await session.get(Category, callback_data.category_id)
    if category is None:
        await callback.answer(texts.ADMIN_CATEGORY_NOT_FOUND, show_alert=True)
        return

    await repo.delete_category(session, category)
    categories = await repo.list_categories(session)
    await callback.message.edit_text(
        texts.admin_categories_screen(categories), reply_markup=admin_categories_kb(categories)
    )
    await callback.answer()
