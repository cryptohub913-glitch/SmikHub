from fastapi import APIRouter, Header, Depends
from sqlalchemy import select
from smikhub.db.engine import get_db_session
from smikhub.db.models import User, Bot, Order
from smikhub.api.webapp_auth import validate_telegram_webapp_data

router = APIRouter(prefix="/api/v1/webapp", tags=["WebApp"])

@router.get("/dashboard")
async def get_dashboard(
    authorization: str = Header(..., alias="X-Telegram-Init-Data"),
    session = Depends(get_db_session)
):
    tg_data = validate_telegram_webapp_data(authorization)
    uid = tg_data.get("user", {}).get("id")
    user = await session.get(User, uid)
    bots = (await session.execute(select(Bot).where(Bot.user_id == uid))).scalars().all()
    orders = (await session.execute(select(Order).where(Order.user_id == uid))).scalars().all()

    return {
        "balance": float(user.balance if user else 0.0),
        "bots": [{"id": b.id, "username": b.username, "is_active": b.is_active} for b in bots],
        "orders": [{"id": o.id, "title": o.title or o.link, "remaining_budget": float(o.remaining_budget)} for o in orders]
    }
