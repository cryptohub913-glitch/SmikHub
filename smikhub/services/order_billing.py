from decimal import Decimal
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from smikhub.db.models import Order
from smikhub.config import BOT_TOKEN

notification_bot = Bot(token=BOT_TOKEN)

async def charge_order_budget(session: AsyncSession, order_id: int, amount: Decimal = None) -> bool:
    order = await session.get(Order, order_id)
    if not order or order.status != "active":
        return False
    price = Decimal(str(order.price_per_sub or 1.0))
    deduct = amount if amount is not None else price
    order.remaining_budget = max(Decimal("0"), Decimal(str(order.remaining_budget or 0)) - deduct)
    if order.remaining_budget < price:
        order.status = "exhausted"
        try:
            await notification_bot.send_message(
                chat_id=order.user_id,
                text=f"⚠️ Бюджет заказа #{order.id} исчерпан. Кампания приостановлена.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    await session.commit()
    return True
