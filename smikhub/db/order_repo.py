from decimal import Decimal
from typing import List
from datetime import datetime, timezone
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from smikhub.db.models import Order, SubscriptionRecord

class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_ranked_sponsor_orders(
        self, user_id: int, lang: str, is_premium: bool, min_price: float, limit: int = 3
    ) -> List[Order]:
        completed_subquery = select(SubscriptionRecord.order_id).where(
            SubscriptionRecord.user_id == user_id,
            SubscriptionRecord.status.in_(["active", "completed"])
        )
        query = (
            select(Order)
            .where(
                Order.status == "active",
                Order.remaining_budget >= Order.price_per_sub,
                Order.price_per_sub >= Decimal(str(min_price)),
                Order.id.not_in(completed_subquery)
            )
            .order_by(desc(Order.price_per_sub), desc(Order.remaining_budget))
            .limit(limit * 2)
        )
        candidates = (await self.session.execute(query)).scalars().all()
        result = []
        for o in candidates:
            if o.target_premium_only and not is_premium:
                continue
            if o.target_languages and o.target_languages != "all":
                if (lang or "ru").lower() not in o.target_languages.lower():
                    continue
            result.append(o)
            if len(result) >= limit:
                break
        return result
