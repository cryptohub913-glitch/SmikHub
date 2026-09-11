import asyncio
from datetime import datetime, timezone

from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.bot import texts
from smikhub.bot.callback_data import StatsCB
from smikhub.bot.handlers.bot_panel import get_owned_bot_or_alert
from smikhub.bot.keyboards import stats_kb
from smikhub.constants import PROVIDER_TITLES
from smikhub.crypto import decrypt
from smikhub.db.models import Provider, SponsorIntegration
from smikhub.services.sponsor_providers import flyer, piarflow, tgrass

router = Router(name="stats")

_SECTION_RENDERERS = {
    Provider.TGRASS: texts.stats_tgrass_section,
    Provider.PIARFLOW: texts.stats_piarflow_section,
    Provider.FLYER: texts.stats_flyer_section,
}


def _fetch_coro(provider: Provider, token: str, today):
    if provider == Provider.TGRASS:
        return tgrass.get_bot_stats(token, today)
    if provider == Provider.PIARFLOW:
        return piarflow.get_bot_stats(token, today)
    return flyer.get_me(token)  # Provider.FLYER


@router.callback_query(StatsCB.filter())
async def show_stats(callback: CallbackQuery, callback_data: StatsCB, session: AsyncSession) -> None:
    bot = await get_owned_bot_or_alert(callback, session, callback_data.bot_id)
    if bot is None:
        return

    today = datetime.now(timezone.utc).date()
    fetchable: list[tuple[Provider, SponsorIntegration]] = [
        (integration.provider, integration)
        for integration in bot.integrations
        if integration.provider in _SECTION_RENDERERS
    ]

    results = await asyncio.gather(
        *(_fetch_coro(provider, decrypt(integration.encrypted_token), today) for provider, integration in fetchable),
        return_exceptions=True,
    )

    sections: list[str] = []
    for (provider, _integration), result in zip(fetchable, results):
        if isinstance(result, Exception):
            sections.append(f"{PROVIDER_TITLES.get(provider.value, provider.value)}\n{texts.STATS_UNAVAILABLE}")
        else:
            sections.append(_SECTION_RENDERERS[provider](result))

    if any(integration.provider == Provider.SUBGRAM for integration in bot.integrations):
        sections.append(texts.STATS_SUBGRAM_UNAVAILABLE)

    await callback.message.edit_text(texts.stats_screen(bot, sections), reply_markup=stats_kb(bot))
    await callback.answer()
