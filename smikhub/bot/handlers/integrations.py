from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import IntegrationCB
from smikhub.bot.handlers.bot_panel import get_owned_bot_or_alert
from smikhub.bot.keyboards import bot_panel_kb, integration_kb
from smikhub.bot.states import IntegrationStates
from smikhub.db import repo
from smikhub.db.models import Provider
from smikhub.services.sponsor_providers import piarflow
from smikhub.services.sponsor_providers.common import SponsorProviderError

router = Router(name="integrations")

_PROVIDER_MAP = {
    "subgram": Provider.SUBGRAM,
    "flyer": Provider.FLYER,
    "tgrass": Provider.TGRASS,
    "piarflow": Provider.PIARFLOW,
}


@router.callback_query(IntegrationCB.filter(F.action == "show"))
async def show_integration(
    callback: CallbackQuery, callback_data: IntegrationCB, session: AsyncSession, state: FSMContext
) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return
    await state.set_state(IntegrationStates.waiting_for_token)
    await state.update_data(bot_id=bot.id, provider=callback_data.provider)
    text = texts.INTEGRATION_TEXTS[callback_data.provider]
    await callback.message.edit_text(text, reply_markup=integration_kb(bot, callback_data.provider))
    await callback.answer()


@router.message(IntegrationStates.waiting_for_token)
async def receive_integration_token(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    bot_id = data.get("bot_id")
    provider_key = data.get("provider")
    token = (message.text or "").strip()

    provider = _PROVIDER_MAP.get(provider_key)
    if bot_id is None or provider is None or not token:
        await message.answer(texts.INTEGRATION_INVALID_TOKEN)
        return

    bot = await repo.get_bot(session, bot_id, owner_id=message.from_user.id)
    if bot is None:
        await state.clear()
        return

    await repo.connect_integration(session, bot, provider, token)
    await state.clear()
    await message.answer(texts.bot_panel(bot), reply_markup=bot_panel_kb(bot))


@router.callback_query(IntegrationCB.filter(F.action == "auto_connect"))
async def auto_connect_piarflow(
    callback: CallbackQuery, callback_data: IntegrationCB, session: AsyncSession, state: FSMContext
) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return

    bot_token = repo.decrypt_bot_token(bot)
    try:
        api_key = await piarflow.register_bot(bot_token, owner_chat_id=callback.from_user.id)
    except SponsorProviderError:
        await callback.answer(texts.PIARFLOW_AUTO_CONNECT_FAILED, show_alert=True)
        return

    await repo.connect_integration(session, bot, Provider.PIARFLOW, api_key)
    await state.clear()
    await callback.message.edit_text(texts.bot_panel(bot), reply_markup=bot_panel_kb(bot))
    await callback.answer(texts.PIARFLOW_AUTO_CONNECT_SUCCESS)
