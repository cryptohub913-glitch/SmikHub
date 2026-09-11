from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import IntegrationsCheckCB
from smikhub.bot.handlers.bot_panel import get_owned_bot_or_alert
from smikhub.bot.keyboards import bot_panel_kb
from smikhub.constants import PROVIDER_TITLES
from smikhub.crypto import decrypt
from smikhub.db.models import Provider
from smikhub.services.sponsor_providers import flyer, piarflow, tgrass
from smikhub.services.sponsor_providers.common import SponsorProviderError

router = Router(name="diagnostics")

_CHECKABLE = {Provider.FLYER, Provider.TGRASS, Provider.PIARFLOW}


async def _check_connection(provider: Provider, token: str) -> None:
    if provider == Provider.TGRASS:
        await tgrass.check_connection(token)
    elif provider == Provider.PIARFLOW:
        await piarflow.check_connection(token)
    else:  # Provider.FLYER — своего check_connection не завёл, get_me уже read-only и падает как надо
        await flyer.get_me(token)


@router.callback_query(IntegrationsCheckCB.filter())
async def check_integrations(
    callback: CallbackQuery, callback_data: IntegrationsCheckCB, session: AsyncSession
) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return

    if not bot.integrations:
        await callback.message.edit_text(texts.integrations_check_none(bot), reply_markup=bot_panel_kb(bot))
        await callback.answer()
        return

    lines: list[str] = []
    for integration in bot.integrations:
        title = PROVIDER_TITLES.get(integration.provider.value, integration.provider.value)
        if integration.provider not in _CHECKABLE:
            lines.append(texts.INTEGRATIONS_CHECK_SUBGRAM)
            continue
        try:
            await _check_connection(integration.provider, decrypt(integration.encrypted_token))
        except SponsorProviderError as error:
            lines.append(texts.integrations_check_error(title, str(error)))
        else:
            lines.append(texts.integrations_check_ok(title))

    await callback.message.edit_text(
        texts.integrations_check_screen(bot, lines), reply_markup=bot_panel_kb(bot)
    )
    await callback.answer()
