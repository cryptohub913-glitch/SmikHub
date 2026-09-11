from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.api.db import get_session
from smikhub.db import repo
from smikhub.db.models import ManagedBot


async def get_authenticated_bot(
    auth: str = Header(..., alias="Auth"),
    session: AsyncSession = Depends(get_session),
) -> ManagedBot:
    bot = await repo.get_bot_by_integration_token(session, auth)
    if bot is None or not bot.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive integration token",
        )
    return bot
