from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.api.db import get_session
from smikhub.config import get_settings
from smikhub.db import platform_repo
from smikhub.db.models import DepositInvoice
from smikhub.services.send_pay import verify_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/send-pay", status_code=status.HTTP_200_OK)
async def send_pay_webhook(
    request: Request,
    signature: str = Header(..., alias="crypto-pay-api-signature"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    settings = get_settings()
    if not settings.send_api_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Send Pay is not configured"
        )

    body = await request.body()
    if not verify_signature(body, signature, settings.send_api_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    payload = await request.json()
    if payload.get("update_type") != "invoice_paid":
        return {"ok": True}

    invoice_payload = payload.get("payload", {})
    send_invoice_id = str(invoice_payload.get("invoice_id"))

    invoice = await platform_repo.get_deposit_invoice_by_send_id(session, send_invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown invoice")

    credited = await platform_repo.mark_deposit_paid(session, invoice)
    if credited:
        await _notify_user_deposit_paid(invoice)

    return {"ok": True}


async def _notify_user_deposit_paid(invoice: DepositInvoice) -> None:
    settings = get_settings()
    bot = Bot(token=settings.bot_token)
    try:
        await bot.send_message(invoice.user_id, f"✅ Баланс пополнен на {invoice.amount} USDT.")
    except TelegramAPIError:
        pass
    finally:
        await bot.session.close()
