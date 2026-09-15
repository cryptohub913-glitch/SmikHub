from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from smikhub.db.models import User, ReferralReward

async def credit_referral_rewards(session: AsyncSession, bot_owner_id: int, earned: Decimal):
    if earned <= Decimal("0"):
        return
    owner = await session.get(User, bot_owner_id)
    if not owner or not owner.referrer_id:
        return
    l1 = await session.get(User, owner.referrer_id)
    if l1:
        reward1 = (earned * Decimal("0.05")).quantize(Decimal("0.0001"))
        if reward1 > Decimal("0"):
            l1.balance = (l1.balance or Decimal("0")) + reward1
            session.add(ReferralReward(referrer_id=l1.id, source_user_id=bot_owner_id, level=1, amount=reward1))
        if l1.referrer_id:
            l2 = await session.get(User, l1.referrer_id)
            if l2:
                reward2 = (earned * Decimal("0.02")).quantize(Decimal("0.0001"))
                if reward2 > Decimal("0"):
                    l2.balance = (l2.balance or Decimal("0")) + reward2
                    session.add(ReferralReward(referrer_id=l2.id, source_user_id=bot_owner_id, level=2, amount=reward2))
    await session.commit()
