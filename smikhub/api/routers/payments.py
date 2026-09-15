from decimal import Decimal
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from smikhub.db.engine import get_db_session
from smikhub.db.models import User, Order
from smikhub.services.cryptobot import CryptoBotService

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])
crypto_svc = CryptoBotService()

@router.post("/cryptobot/webhook")
async def cryptobot_webhook(
    request: Request,
    signature: str = Header(..., alias="crypto-pay-api-signature"),
    session = Depends(get_db_session)
):
    body = await request.body()
    if not crypto_svc.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    event = await request.json()
    if event.get("update_type") == "invoice_paid":
        payload = event["payload"].get("payload", "").split(":")
        if len(payload) >= 3 and payload[0] == "topup":
            uid = int(payload[1])
            oid = int(payload[2])
            amount = Decimal(str(event["payload"]["amount"]))
            if oid > 0:
                ord_item = await session.get(Order, oid)
                if ord_item:
                    ord_item.remaining_budget = (ord_item.remaining_budget or Decimal("0")) + amount
                    if ord_item.status == "exhausted":
                        ord_item.status = "active"
            else:
                user = await session.get(User, uid)
                if user:
                    user.balance = (user.balance or Decimal("0")) + amount
            await session.commit()
    return {"ok": True}
