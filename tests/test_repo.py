from decimal import Decimal

import pytest

from smikhub.db import repo
from smikhub.db.models import CategoryMode, Provider
from tests.conftest import TEST_OWNER_ID


async def _make_bot(session, telegram_bot_id: int = 42, username: str = "test_bot"):
    await repo.get_or_create_user(session, TEST_OWNER_ID)
    return await repo.create_bot(
        session,
        owner_id=TEST_OWNER_ID,
        telegram_bot_id=telegram_bot_id,
        username=username,
        bot_token="123456:AAAABBBBCCCC",
        default_min_price=Decimal("0.0"),
        default_max_sponsors=3,
    )


@pytest.mark.asyncio
async def test_create_bot_has_defaults_and_native_priority(session):
    bot = await _make_bot(session)

    assert bot.username == "test_bot"
    assert bot.is_active is True
    assert bot.category_mode == CategoryMode.ALL_EXCEPT_OWN
    assert Decimal(bot.min_price) == Decimal("0.0")
    assert bot.max_sponsors == 3
    assert [p.provider for p in bot.priorities] == ["botohub"]
    assert bot.integrations == []
    assert bot.disabled_categories == []


@pytest.mark.asyncio
async def test_integration_token_round_trips_and_is_not_stored_plain(session):
    bot = await _make_bot(session)

    assert bot.integration_token_encrypted != ""
    decrypted = repo.decrypt_integration_token(bot)
    assert decrypted
    # The stored value must not be the plaintext token itself.
    assert bot.integration_token_encrypted != decrypted

    fetched = await repo.get_bot_by_integration_token(session, decrypted)
    assert fetched is not None
    assert fetched.id == bot.id


@pytest.mark.asyncio
async def test_toggle_disabled_category_adds_and_removes(session):
    bot = await _make_bot(session)
    categories = await repo.list_categories(session)
    category = categories[0]

    await repo.toggle_disabled_category(session, bot, category.id)
    assert len(bot.disabled_categories) == 1

    await repo.toggle_disabled_category(session, bot, category.id)
    assert len(bot.disabled_categories) == 0


@pytest.mark.asyncio
async def test_connect_integration_adds_priority_entry(session):
    bot = await _make_bot(session)

    await repo.connect_integration(session, bot, Provider.SUBGRAM, "subgram-token")

    assert len(bot.integrations) == 1
    assert bot.integrations[0].provider == Provider.SUBGRAM
    providers = {p.provider for p in bot.priorities}
    assert providers == {"botohub", "subgram"}


@pytest.mark.asyncio
async def test_move_priority_swaps_positions(session):
    bot = await _make_bot(session)
    await repo.connect_integration(session, bot, Provider.SUBGRAM, "subgram-token")

    ordered_before = [p.provider for p in sorted(bot.priorities, key=lambda p: p.position)]
    assert ordered_before == ["botohub", "subgram"]

    await repo.move_priority(session, bot, "subgram", direction=-1)

    ordered_after = [p.provider for p in sorted(bot.priorities, key=lambda p: p.position)]
    assert ordered_after == ["subgram", "botohub"]


@pytest.mark.asyncio
async def test_move_priority_out_of_bounds_is_noop(session):
    bot = await _make_bot(session)
    ordered_before = [p.provider for p in sorted(bot.priorities, key=lambda p: p.position)]

    await repo.move_priority(session, bot, "botohub", direction=-1)

    ordered_after = [p.provider for p in sorted(bot.priorities, key=lambda p: p.position)]
    assert ordered_after == ordered_before


@pytest.mark.asyncio
async def test_delete_bot_removes_it(session):
    bot = await _make_bot(session)
    bot_id = bot.id

    await repo.delete_bot(session, bot)

    assert await repo.get_bot(session, bot_id) is None


@pytest.mark.asyncio
async def test_list_user_bots_scoped_to_owner(session):
    await _make_bot(session, telegram_bot_id=1, username="bot_one")
    await repo.get_or_create_user(session, TEST_OWNER_ID + 1)
    await repo.create_bot(
        session,
        owner_id=TEST_OWNER_ID + 1,
        telegram_bot_id=2,
        username="bot_two",
        bot_token="654321:XXXXYYYYZZZZ",
        default_min_price=Decimal("0.0"),
        default_max_sponsors=3,
    )

    bots = await repo.list_user_bots(session, TEST_OWNER_ID)

    assert [b.username for b in bots] == ["bot_one"]
