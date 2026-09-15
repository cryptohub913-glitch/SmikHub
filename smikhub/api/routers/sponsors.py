import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from smikhub.db.models import Bot, Order
from smikhub.api.deps import get_db

# Обрати внимание, префикс может быть просто "/", если он уже задан в main.py
router = APIRouter(prefix="/api/v1/bot", tags=["Sponsors"])

async def get_current_bot(
    authorization: str = Header(None), 
    db: AsyncSession = Depends(get_db)
):
    
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.split(" ")[1]
    bot = (await db.execute(select(Bot).where(Bot.integration_token == token))).scalar_one_or_none()
    
    if not bot or not bot.is_active:
        raise HTTPException(status_code=403, detail="Bot not found or banned by admin")
    return bot


@router.get("/sponsors")
async def get_bot_sponsors(
    user_id: int, 
    bot: Bot = Depends(get_current_bot), 
    db: AsyncSession = Depends(get_db)
):
    sponsors = []
    
    # =======================================================
    # ПРИОРИТЕТ 1: Внутренние заказы SmikHub (твоя база)
    # =======================================================
    # Ищем активные заказы, где денег хватает хотя бы на 1 подписку
    stmt = select(Order).where(
        Order.status == "active",
        Order.remaining_budget >= Order.price_per_sub
    ).limit(bot.max_sponsors)
    
    internal_orders = (await db.execute(stmt)).scalars().all()
    
    for order in internal_orders:
        sponsors.append({
            "id": f"smikhub_{order.id}",
            "name": order.title or order.channel_username or "Спонсор",
            "url": order.link,
            "reward": float(bot.min_price),  # Вознаграждение по тарифу бота
            "source": "smikhub"
        })
        
    # Если мы нашли свои заказы, сразу отдаем их.
    if sponsors:
        return {"sponsors": sponsors}

    # =======================================================
    # ПРИОРИТЕТ 2: Сторонние интеграции (Waterfall)
    # =======================================================
    # Используем aiohttp вместо httpx
    timeout = aiohttp.ClientTimeout(total=3.0)
    async with aiohttp.ClientSession(timeout=timeout) as client:
        
        # 1. Проверяем Subgram
        if bot.subgram_token:
            try:
                async with client.get(
                    "https://api.subgram.org/api/sponsors",
                    headers={"Authorization": f"Bearer {bot.subgram_token}"},
                    params={"user_id": user_id}
                ) as res:
                    if res.status == 200:
                        data = await res.json()
                        for sp in data.get("sponsors", []):
                            sponsors.append({
                                "id": f"subgram_{sp.get('id')}",
                                "name": sp.get("name", "Спонсор"),
                                "url": sp.get("url"),
                                "reward": float(bot.min_price),
                                "source": "subgram"
                            })
                        if sponsors: return {"sponsors": sponsors}
            except Exception: pass

        # 2. Проверяем Flyer
        if bot.flyer_token:
            try:
                async with client.get(
                    "https://api.flyerhubs.com/sponsors", 
                    headers={"Authorization": f"Bearer {bot.flyer_token}"},
                    params={"user_id": user_id}
                ) as res:
                    if res.status == 200:
                        data = await res.json()
                        for sp in data.get("sponsors", data.get("data", [])):
                            sponsors.append({
                                "id": f"flyer_{sp.get('id')}",
                                "name": sp.get("title", sp.get("name", "Спонсор")),
                                "url": sp.get("link", sp.get("url")),
                                "reward": float(bot.min_price),
                                "source": "flyer"
                            })
                        if sponsors: return {"sponsors": sponsors}
            except Exception: pass

        # 3. Проверяем Traffy (Trafsly)
        if bot.traffy_token:
            try:
                async with client.get(
                    "https://api.trafsly.com/api/v1/sponsors",
                    headers={"Authorization": f"Bearer {bot.traffy_token}"},
                    params={"user_id": user_id}
                ) as res:
                    if res.status == 200:
                        data = await res.json()
                        for sp in data.get("sponsors", data.get("data", [])):
                            sponsors.append({
                                "id": f"traffy_{sp.get('id')}",
                                "name": sp.get("title", sp.get("name", "Спонсор")),
                                "url": sp.get("link", sp.get("url")),
                                "reward": float(bot.min_price),
                                "source": "traffy"
                            })
                        if sponsors: return {"sponsors": sponsors}
            except Exception: pass

        # 4. Проверяем PiarFlow
        if bot.piarflow_token:
            try:
                async with client.get(
                    "https://piarflow.com/api/v1/sponsors",
                    headers={"Authorization": f"Bearer {bot.piarflow_token}"},
                    params={"user_id": user_id}
                ) as res:
                    if res.status == 200:
                        data = await res.json()
                        for sp in data.get("sponsors", data.get("data", [])):
                            sponsors.append({
                                "id": f"piarflow_{sp.get('id')}",
                                "name": sp.get("title", sp.get("name", "Спонсор")),
                                "url": sp.get("link", sp.get("url")),
                                "reward": float(bot.min_price),
                                "source": "piarflow"
                            })
                        if sponsors: return {"sponsors": sponsors}
            except Exception: pass

        # 5. Проверяем TgGrass
        if bot.tgrass_token:
            try:
                async with client.get(
                    "https://tgrass.space/api/v1/sponsors",
                    headers={"Authorization": f"Bearer {bot.tgrass_token}"},
                    params={"user_id": user_id}
                ) as res:
                    if res.status == 200:
                        data = await res.json()
                        for sp in data.get("sponsors", data.get("data", [])):
                            sponsors.append({
                                "id": f"tgrass_{sp.get('id')}",
                                "name": sp.get("title", sp.get("name", "Спонсор")),
                                "url": sp.get("link", sp.get("url")),
                                "reward": float(bot.min_price),
                                "source": "tgrass"
                            })
                        if sponsors: return {"sponsors": sponsors}
            except Exception: pass

    # Если ни внутренних заказов, ни рабочих интеграций нет — отдаём пустой список
    return {"sponsors": []}