import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from smikhub.db.models import SubscriptionRecord

async def run_retention_worker(check_bot, session_maker):
    while True:
        await asyncio.sleep(600)  # Каждые 10 минут
        try:
            async with session_maker() as session:
                ten_mins_ago = datetime.utcnow() - timedelta(minutes=10)
                records = (await session.execute(
                    select(SubscriptionRecord).where(
                        SubscriptionRecord.status == "completed",
                        SubscriptionRecord.checked_retention == False,
                        SubscriptionRecord.joined_at <= ten_mins_ago
                    ).limit(50)
                )).scalars().all()

                for r in records:
                    r.checked_retention = True
                await session.commit()
        except Exception:
            pass
