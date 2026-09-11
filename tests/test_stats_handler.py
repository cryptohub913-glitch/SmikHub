from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from smikhub.bot.callback_data import StatsCB
from smikhub.bot.handlers import stats
from smikhub.db import repo
from smikhub.db.models import Provider
from smikhub.services.sponsor_providers.common import SponsorProviderError
from smikhub.services.sponsor_providers.piarflow import BotStats as PiarflowBotStats
from smikhub.services.sponsor_providers.tgrass import BotStats as TgrassBotStats
from tests.conftest import TEST_OWNER_ID


def _make_callback() -> MagicMock:
    callback = MagicMock()
    callback.from_user = SimpleNamespace(id=TEST_OWNER_ID)
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


async def _make_bot(session, *providers: Provider):
    await repo.get_or_create_user(session, TEST_OWNER_ID)
    bot = await repo.create_bot(
        session,
        owner_id=TEST_OWNER_ID,
        telegram_bot_id=1,
        username="stats_test_bot",
        bot_token="123456:AAAA",
        default_min_price=Decimal("0.0"),
        default_max_sponsors=3,
    )
    for provider in providers:
        await repo.connect_integration(session, bot, provider, f"{provider.value}-key")
    return await repo.get_bot(session, bot.id)


@pytest.mark.asyncio
async def test_stats_shows_placeholder_when_no_providers_connected(session):
    bot = await _make_bot(session)

    callback = _make_callback()
    await stats.show_stats(callback, StatsCB(bot_id=bot.id), session)

    sent_text = callback.message.edit_text.await_args.args[0]
    assert "Подключите" in sent_text


@pytest.mark.asyncio
async def test_stats_renders_real_tgrass_and_piarflow_numbers(session, monkeypatch):
    bot = await _make_bot(session, Provider.TGRASS, Provider.PIARFLOW)

    monkeypatch.setattr(
        stats.tgrass,
        "get_bot_stats",
        AsyncMock(
            return_value=TgrassBotStats(
                balance=Decimal("10"), subs_count=5, unsubs_count=1, income=Decimal("2.5")
            )
        ),
    )
    monkeypatch.setattr(
        stats.piarflow,
        "get_bot_stats",
        AsyncMock(
            return_value=PiarflowBotStats(
                balance=Decimal("20"), subs_count=3, unsubs_count=0, income=Decimal("1.0")
            )
        ),
    )

    callback = _make_callback()
    await stats.show_stats(callback, StatsCB(bot_id=bot.id), session)

    sent_text = callback.message.edit_text.await_args.args[0]
    assert "Tgrass" in sent_text
    assert "10" in sent_text
    assert "PiarFlow" in sent_text
    assert "20" in sent_text


@pytest.mark.asyncio
async def test_stats_shows_unavailable_when_provider_call_fails(session, monkeypatch):
    bot = await _make_bot(session, Provider.TGRASS)

    monkeypatch.setattr(stats.tgrass, "get_bot_stats", AsyncMock(side_effect=SponsorProviderError("down")))

    callback = _make_callback()
    await stats.show_stats(callback, StatsCB(bot_id=bot.id), session)

    sent_text = callback.message.edit_text.await_args.args[0]
    assert "недоступны" in sent_text


@pytest.mark.asyncio
async def test_stats_notes_subgram_has_no_api(session):
    bot = await _make_bot(session, Provider.SUBGRAM)

    callback = _make_callback()
    await stats.show_stats(callback, StatsCB(bot_id=bot.id), session)

    sent_text = callback.message.edit_text.await_args.args[0]
    assert "Subgram" in sent_text
    assert "нет документации" in sent_text


@pytest.mark.asyncio
async def test_stats_renders_flyer_key_status(session, monkeypatch):
    bot = await _make_bot(session, Provider.FLYER)

    monkeypatch.setattr(
        stats.flyer, "get_me", AsyncMock(return_value={"bot_id": 42, "webhook": None, "status": True})
    )

    callback = _make_callback()
    await stats.show_stats(callback, StatsCB(bot_id=bot.id), session)

    sent_text = callback.message.edit_text.await_args.args[0]
    assert "Flyer" in sent_text
    assert "42" in sent_text
