from decimal import Decimal
from typing import List
from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from smikhub.db.engine import get_db_session
from smikhub.db.models import Bot, Order, SubscriptionRecord
from smikhub.db.order_repo import OrderRepository
from smikhub.services.rate_limiter import check_limiter
from smikhub.services.antifraud import AntiFraudEngine
from smikhub.services.order_billing import charge_order_budget
from smikhub.services.referrals import credit_referral_rewards
from smikhub.services.postback import PostbackService

router = APIRouter(prefix="/api/v1/bot/sponsors", tags=["Sponsors"])

class CheckTaskItem(BaseModel):
    provider: str = "botohub"
    task_id: str

class SponsorCheckPayload(BaseModel):
    user_id: int
    tasks: List[CheckTaskItem]

@router.get("")
async def get_sponsors(
    user_id: int,
    lang: str = "ru",
    is_premium: str = "false",
    auth: str = Header(...),
    session = Depends(get_db_session)
):
    bot_res = await session.execute(select(Bot).where(Bot.integration_token == auth))
    bot = bot_res.scalars().first()
    if not bot or not bot.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    repo = OrderRepository(session)
    orders = await repo.get_ranked_sponsor_orders(
        user_id=user_id,
        lang=lang,
        is_premium=(is_premium.lower() == "true"),
        min_price=float(bot.min_price or 0.0),
        limit=bot.max_sponsors
    )

    return [
        {
            "provider": "botohub",
            "task_id": str(o.id),
            "title": o.title or o.link,
            "link": o.link,
            "price": str(o.price_per_sub)
        }
        for o in orders
    ]

@router.post("/check")
async def check_sponsors(
    payload: SponsorCheckPayload,
    auth: str = Header(...),
    session = Depends(get_db_session)
):
    bot = (await session.execute(select(Bot).where(Bot.integration_token == auth))).scalars().first()
    if not bot or not bot.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    is_throttled, cached = check_limiter.check_throttle(bot.id, payload.user_id, [t.dict() for t in payload.tasks])
    if is_throttled:
        return cached

    is_fraud, _ = await AntiFraudEngine.evaluate_user_risk(session, payload.user_id)
    results = []

    for t in payload.tasks:
        if is_fraud:
            results.append({"provider": t.provider, "task_id": t.task_id, "status": "failed"})
            continue
        try:
            oid = int(t.task_id)
            ord_item = await session.get(Order, oid)
            if ord_item and ord_item.status == "active":
                payout = Decimal(str(ord_item.price_per_sub))
                rec = SubscriptionRecord(
                    order_id=ord_item.id,
                    bot_id=bot.id,
                    user_id=payload.user_id,
                    payout_amount=payout,
                    status="completed"
                )
                session.add(rec)
                await charge_order_budget(session, ord_item.id, payout)
                await credit_referral_rewards(session, bot.user_id, payout)
                await PostbackService.trigger_task_completed(bot, payload.user_id, t.task_id, "botohub", float(payout))
                results.append({"provider": t.provider, "task_id": t.task_id, "status": "completed"})
            else:
                results.append({"provider": t.provider, "task_id": t.task_id, "status": "completed"})
        except Exception:
            results.append({"provider": t.provider, "task_id": t.task_id, "status": "completed"})

    await session.commit()
    check_limiter.record_result(bot.id, payload.user_id, results)
    return results
