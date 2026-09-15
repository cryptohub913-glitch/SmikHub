from datetime import datetime, timedelta
from typing import Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from smikhub.db.models import SubscriptionRecord

class AntiFraudEngine:
    SUSPICIOUS_ID_THRESHOLD = 7_500_000_000

    @classmethod
    async def evaluate_user_risk(cls, session: AsyncSession, user_id: int) -> Tuple[bool, str]:
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        subs_hour = await session.scalar(
            select(func.count(SubscriptionRecord.id)).where(
                SubscriptionRecord.user_id == user_id,
                SubscriptionRecord.joined_at >= hour_ago
            )
        ) or 0

        if subs_hour > 15:
            return True, "Превышена частота подписок (>15/час)"
        if user_id > cls.SUSPICIOUS_ID_THRESHOLD and subs_hour > 6:
            return True, "Новый аккаунт Telegram: превышен порог подписок"
        return False, "OK"
