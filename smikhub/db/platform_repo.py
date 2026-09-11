from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from smikhub.db.models import (
    DepositInvoice,
    DepositStatus,
    ManagedBot,
    Order,
    PlatformSettings,
    SponsorIntegration,
    User,
    WithdrawalRequest,
    WithdrawalStatus,
)


async def get_platform_settings(session: AsyncSession) -> PlatformSettings:
    settings = await session.get(PlatformSettings, 1)
    if settings is None:
        settings = PlatformSettings(id=1)
        session.add(settings)
        await session.commit()
    return settings


async def toggle_sell_ap_enabled(session: AsyncSession, settings: PlatformSettings) -> None:
    settings.sell_ap_enabled = not settings.sell_ap_enabled
    await session.commit()


async def toggle_buy_ap_enabled(session: AsyncSession, settings: PlatformSettings) -> None:
    settings.buy_ap_enabled = not settings.buy_ap_enabled
    await session.commit()


#: Числовые поля PlatformSettings, редактируемые из "⚙️ Настройки → 💰 Цены и лимиты".
#: label — подпись в списке настроек, kind — "decimal" или "int" (как парсить ввод админа).
EDITABLE_NUMERIC_FIELDS: dict[str, tuple[str, str]] = {
    "min_deposit_amount": ("Мин. сумма пополнения", "decimal"),
    "min_withdrawal_amount": ("Мин. сумма вывода", "decimal"),
    "sell_price_grid_min": ('Мин. цена сетки "Продать ОП"', "decimal"),
    "sell_price_grid_max": ('Макс. цена сетки "Продать ОП"', "decimal"),
    "sell_default_min_price": ("Цена по умолчанию для новых ботов", "decimal"),
    "sell_sponsors_grid_min": ('Мин. значение сетки "Макс. спонсоров"', "int"),
    "sell_sponsors_grid_max": ('Макс. значение сетки "Макс. спонсоров"', "int"),
    "sell_default_max_sponsors": ("Спонсоров по умолчанию для новых ботов", "int"),
    "buy_price_grid_min": ('Мин. цена сетки "Купить ОП"', "decimal"),
    "buy_price_grid_max": ('Макс. цена сетки "Купить ОП"', "decimal"),
}


async def set_platform_field(
    session: AsyncSession, settings: PlatformSettings, field: str, value: Decimal | int
) -> None:
    if field not in EDITABLE_NUMERIC_FIELDS:
        raise ValueError(f"Unknown platform settings field: {field}")
    setattr(settings, field, value)
    await session.commit()


async def create_deposit_invoice(
    session: AsyncSession, user_id: int, send_invoice_id: str, amount: Decimal
) -> DepositInvoice:
    invoice = DepositInvoice(user_id=user_id, send_invoice_id=send_invoice_id, amount=amount)
    session.add(invoice)
    await session.commit()
    return invoice


async def get_deposit_invoice_by_send_id(
    session: AsyncSession, send_invoice_id: str
) -> DepositInvoice | None:
    result = await session.execute(
        select(DepositInvoice).where(DepositInvoice.send_invoice_id == send_invoice_id)
    )
    return result.scalars().one_or_none()


async def mark_deposit_paid(session: AsyncSession, invoice: DepositInvoice) -> bool:
    """Идемпотентно помечает счёт оплаченным и зачисляет баланс. Возвращает False, если
    счёт уже был оплачен ранее (повтор вебхука) — баланс повторно не зачисляется."""
    if invoice.status == DepositStatus.PAID:
        return False

    invoice.status = DepositStatus.PAID
    invoice.paid_at = datetime.now(timezone.utc)

    owner = await session.get(User, invoice.user_id)
    owner.balance = Decimal(str(owner.balance)) + Decimal(str(invoice.amount))
    await session.commit()
    return True


async def create_withdrawal_request(session: AsyncSession, user: User, amount: Decimal) -> WithdrawalRequest:
    """Сразу резервирует (списывает) баланс, чтобы заявку нельзя было потратить дважды,
    пока она ожидает решения админа."""
    user.balance = Decimal(str(user.balance)) - amount
    request = WithdrawalRequest(user_id=user.id, amount=amount, spend_id="pending")
    session.add(request)
    await session.flush()
    request.spend_id = f"withdrawal-{request.id}"
    await session.commit()
    return request


async def get_withdrawal(session: AsyncSession, withdrawal_id: int) -> WithdrawalRequest | None:
    return await session.get(WithdrawalRequest, withdrawal_id)


async def list_pending_withdrawals(session: AsyncSession) -> list[WithdrawalRequest]:
    result = await session.execute(
        select(WithdrawalRequest)
        .where(WithdrawalRequest.status == WithdrawalStatus.PENDING)
        .order_by(WithdrawalRequest.created_at)
    )
    return list(result.scalars())


async def approve_withdrawal(session: AsyncSession, withdrawal: WithdrawalRequest, admin_id: int) -> None:
    withdrawal.status = WithdrawalStatus.APPROVED
    withdrawal.decided_at = datetime.now(timezone.utc)
    withdrawal.decided_by = admin_id
    await session.commit()


async def reject_withdrawal(session: AsyncSession, withdrawal: WithdrawalRequest, admin_id: int) -> None:
    owner = await session.get(User, withdrawal.user_id)
    owner.balance = Decimal(str(owner.balance)) + Decimal(str(withdrawal.amount))
    withdrawal.status = WithdrawalStatus.REJECTED
    withdrawal.decided_at = datetime.now(timezone.utc)
    withdrawal.decided_by = admin_id
    await session.commit()


async def toggle_ban(session: AsyncSession, user: User) -> None:
    user.is_banned = not user.is_banned
    await session.commit()


async def adjust_balance(session: AsyncSession, user: User, delta: Decimal) -> None:
    user.balance = Decimal(str(user.balance)) + delta
    await session.commit()


async def list_bots_admin(session: AsyncSession, limit: int = 20) -> list[ManagedBot]:
    result = await session.execute(
        select(ManagedBot)
        .options(selectinload(ManagedBot.owner))
        .order_by(ManagedBot.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def platform_stats(session: AsyncSession) -> dict[str, object]:
    users_count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    bots_count = (await session.execute(select(func.count()).select_from(ManagedBot))).scalar_one()
    orders_count = (await session.execute(select(func.count()).select_from(Order))).scalar_one()

    total_spent = (await session.execute(select(func.coalesce(func.sum(Order.spent), 0)))).scalar_one()
    total_deposits = (
        await session.execute(
            select(func.coalesce(func.sum(DepositInvoice.amount), 0)).where(
                DepositInvoice.status == DepositStatus.PAID
            )
        )
    ).scalar_one()
    total_withdrawals = (
        await session.execute(
            select(func.coalesce(func.sum(WithdrawalRequest.amount), 0)).where(
                WithdrawalRequest.status == WithdrawalStatus.APPROVED
            )
        )
    ).scalar_one()

    return {
        "users_count": users_count,
        "bots_count": bots_count,
        "orders_count": orders_count,
        "total_spent": Decimal(str(total_spent)),
        "total_deposits": Decimal(str(total_deposits)),
        "total_withdrawals": Decimal(str(total_withdrawals)),
    }


async def count_integrations_by_provider(session: AsyncSession) -> dict[str, int]:
    """Сколько ботов платформы имеют подключённой каждую сеть — просто `GROUP BY provider`,
    без единого живого запроса к внешним API (чтобы открытие экрана диагностики не заваливало
    Flyer/Tgrass/PiarFlow запросами разом за все боты платформы)."""
    result = await session.execute(
        select(SponsorIntegration.provider, func.count())
        .select_from(SponsorIntegration)
        .group_by(SponsorIntegration.provider)
    )
    return {provider.value: count for provider, count in result.all()}


async def user_profile_stats(session: AsyncSession, user_id: int) -> dict[str, object] | None:
    user = await session.get(User, user_id)
    if user is None:
        return None

    bots_count = (
        await session.execute(select(func.count()).select_from(ManagedBot).where(ManagedBot.owner_id == user_id))
    ).scalar_one()
    orders_count = (
        await session.execute(select(func.count()).select_from(Order).where(Order.owner_id == user_id))
    ).scalar_one()
    total_spent = (
        await session.execute(
            select(func.coalesce(func.sum(Order.spent), 0)).where(Order.owner_id == user_id)
        )
    ).scalar_one()
    deposits_paid = (
        await session.execute(
            select(func.count())
            .select_from(DepositInvoice)
            .where(DepositInvoice.user_id == user_id, DepositInvoice.status == DepositStatus.PAID)
        )
    ).scalar_one()
    withdrawals_approved = (
        await session.execute(
            select(func.count())
            .select_from(WithdrawalRequest)
            .where(WithdrawalRequest.user_id == user_id, WithdrawalRequest.status == WithdrawalStatus.APPROVED)
        )
    ).scalar_one()

    return {
        "user": user,
        "bots_count": bots_count,
        "orders_count": orders_count,
        "total_spent": Decimal(str(total_spent)),
        "deposits_paid": deposits_paid,
        "withdrawals_approved": withdrawals_approved,
    }
