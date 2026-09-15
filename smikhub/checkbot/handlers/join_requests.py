from aiogram import Router
from aiogram.types import ChatJoinRequest

router = Router()

@router.chat_join_request()
async def auto_approve(event: ChatJoinRequest):
    try:
        await event.approve()
    except Exception:
        pass
