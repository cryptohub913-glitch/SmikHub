from aiogram import Router
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberUpdated

from smikhub.db import order_repo
from smikhub.db.engine import get_session_factory

router = Router(name="checkbot")

_MEMBER_STATUSES = {ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED}
_LEFT_STATUSES = {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}


@router.chat_member()
async def on_chat_member_update(update: ChatMemberUpdated) -> None:
    old_status = update.old_chat_member.status
    new_status = update.new_chat_member.status
    telegram_user_id = update.new_chat_member.user.id

    became_member = old_status not in _MEMBER_STATUSES and new_status in _MEMBER_STATUSES
    left = old_status in _MEMBER_STATUSES and new_status in _LEFT_STATUSES

    if not became_member and not left:
        return

    telegram_username = update.new_chat_member.user.username

    async with get_session_factory()() as session:
        orders = await order_repo.get_running_orders_for_chat(session, update.chat.id)
        for order in orders:
            if became_member:
                await order_repo.record_join_event(session, order, telegram_user_id, telegram_username)
            else:
                await order_repo.record_leave_event(session, order, telegram_user_id)
