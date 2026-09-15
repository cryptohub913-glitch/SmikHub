from fastapi import APIRouter, Response, Depends
from sqlalchemy import select, func
from smikhub.db.engine import get_db_session
from smikhub.db.models import User, Bot, Order, SubscriptionRecord

router = APIRouter(tags=["Metrics"])

@router.get("/metrics")
async def prometheus_metrics(session = Depends(get_db_session)):
    u_count = await session.scalar(select(func.count(User.id))) or 0
    b_count = await session.scalar(select(func.count(Bot.id))) or 0
    o_count = await session.scalar(select(func.count(Order.id)).where(Order.status == "active")) or 0
    s_count = await session.scalar(select(func.count(SubscriptionRecord.id)).where(SubscriptionRecord.status == "completed")) or 0

    text = f'''smikhub_users_total {u_count}
smikhub_active_bots_count {b_count}
smikhub_active_orders_count {o_count}
smikhub_subscriptions_completed_total {s_count}
'''
    return Response(content=text, media_type="text/plain")
