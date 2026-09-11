from fastapi import APIRouter, Depends

from smikhub.api.deps import get_authenticated_bot
from smikhub.api.schemas import BotConfigResponse
from smikhub.db.models import ManagedBot

router = APIRouter(prefix="/api/v1/bot", tags=["bot"])


@router.get("/config", response_model=BotConfigResponse)
async def get_bot_config(bot: ManagedBot = Depends(get_authenticated_bot)) -> BotConfigResponse:
    ordered_priorities = sorted(bot.priorities, key=lambda p: p.position)
    return BotConfigResponse(
        bot_username=bot.username,
        is_active=bot.is_active,
        category_mode=bot.category_mode.value,
        min_price=bot.min_price,
        max_sponsors=bot.max_sponsors,
        disabled_categories=[dc.category.code for dc in bot.disabled_categories],
        provider_priority=[p.provider for p in ordered_priorities],
    )
