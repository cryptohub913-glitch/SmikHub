from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import aiohttp

from smikhub.db.models import Bot, Order
from smikhub.config import DATABASE_URL, BOT_TOKEN

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session_maker() as session:
        yield session

router = APIRouter(prefix="/api/v1/bot", tags=["Verification"])

@router.post("/verify-subscription")
async def verify_subscription(data: dict, db: AsyncSession = Depends(get_db)):
    """
    Ожидает JSON: {"user_id": 12345, "order_id": "smikhub_5"}
    Проверяет через Telegram Bot API, подписан ли юзер на канал.
    """
    user_id = data.get("user_id")
    order_id_str = data.get("order_id")
    
    if not user_id or not order_id_str or not order_id_str.startswith("smikhub_"):
        raise HTTPException(status_code=400, detail="Invalid parameters")
        
    order_id = int(order_id_str.replace("smikhub_", ""))
    order = await db.get(Order, order_id)
    
    if not order or order.status != "active":
        return {"success": False, "error": "Order not found or inactive"}

    # Извлекаем chat_id или юзернейм канала из ссылки (например, https://t.me/mychannel -> @mychannel)
    channel_username = order.channel_link.rstrip("/").split("/")[-1]
    if not channel_username.startswith("@"):
        channel_username = "@" + channel_username

    # Запрос к Telegram Bot API для проверки членства в чате/канале
    async with aiohttp.ClientSession() as client:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        async with client.get(url, params={"chat_id": channel_username, "user_id": user_id}) as res:
            if res.status == 200:
                result = await res.json()
                status = result.get("result", {}).get("status")
                # Статусы реального участника: creator, administrator, member
                if status in ["creator", "administrator", "member"]:
                    # Списываем стоимость подписки с остатка бюджета заказа
                    if order.remaining_budget >= order.cpc_price:
                        order.remaining_budget -= order.cpc_price
                        if order.remaining_budget < order.cpc_price:
                            order.status = "completed" # Бюджет исчерпан
                        await db.commit()
                        return {"success": True, "reward_paid": float(order.cpc_price)}
                        
            return {"success": False, "error": "User is not subscribed"}