import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from smikhub.constants import NATIVE_PROVIDER
from smikhub.crypto import decrypt, encrypt, generate_integration_token, sha256_hex
from smikhub.db.models import (
    BotDisabledCategory,
    Category,
    CategoryMode,
    ManagedBot,
    Provider,
    ProviderPriority,
    SponsorIntegration,
    User,
)


def _bot_query():
    return select(ManagedBot).options(
        selectinload(ManagedBot.disabled_categories).selectinload(BotDisabledCategory.category),
        selectinload(ManagedBot.integrations),
        selectinload(ManagedBot.priorities),
    )


async def get_or_create_user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        user = User(id=user_id)
        session.add(user)
        await session.commit()
    return user


async def list_user_bots(session: AsyncSession, owner_id: int) -> list[ManagedBot]:
    result = await session.execute(_bot_query().where(ManagedBot.owner_id == owner_id))
    return list(result.scalars().unique())


async def get_bot(session: AsyncSession, bot_id: int, owner_id: int | None = None) -> ManagedBot | None:
    query = _bot_query().where(ManagedBot.id == bot_id)
    if owner_id is not None:
        query = query.where(ManagedBot.owner_id == owner_id)
    result = await session.execute(query)
    return result.scalars().unique().one_or_none()


async def get_bot_by_telegram_id(session: AsyncSession, telegram_bot_id: int) -> ManagedBot | None:
    result = await session.execute(
        select(ManagedBot).where(ManagedBot.telegram_bot_id == telegram_bot_id)
    )
    return result.scalars().one_or_none()


async def get_bot_by_integration_token(session: AsyncSession, integration_token: str) -> ManagedBot | None:
    token_hash = sha256_hex(integration_token)
    result = await session.execute(
        _bot_query().where(ManagedBot.integration_token_hash == token_hash)
    )
    return result.scalars().unique().one_or_none()


async def create_bot(
    session: AsyncSession,
    owner_id: int,
    telegram_bot_id: int,
    username: str,
    bot_token: str,
    default_min_price: Decimal,
    default_max_sponsors: int,
) -> ManagedBot:
    integration_token = generate_integration_token()
    bot = ManagedBot(
        owner_id=owner_id,
        telegram_bot_id=telegram_bot_id,
        username=username,
        encrypted_token=encrypt(bot_token),
        min_price=default_min_price,
        max_sponsors=default_max_sponsors,
        integration_token_hash=sha256_hex(integration_token),
        integration_token_encrypted=encrypt(integration_token),
        disabled_categories=[],
        integrations=[],
        priorities=[ProviderPriority(provider=NATIVE_PROVIDER, position=0)],
    )
    session.add(bot)
    await session.commit()
    return bot


async def delete_bot(session: AsyncSession, bot: ManagedBot) -> None:
    await session.delete(bot)
    await session.commit()


def decrypt_integration_token(bot: ManagedBot) -> str:
    return decrypt(bot.integration_token_encrypted)


def decrypt_bot_token(bot: ManagedBot) -> str:
    return decrypt(bot.encrypted_token)


async def set_category_mode(session: AsyncSession, bot: ManagedBot, mode: CategoryMode) -> None:
    bot.category_mode = mode
    await session.commit()


async def set_min_price(session: AsyncSession, bot: ManagedBot, price: Decimal) -> None:
    bot.min_price = price
    await session.commit()


async def set_max_sponsors(session: AsyncSession, bot: ManagedBot, count: int) -> None:
    bot.max_sponsors = count
    await session.commit()


async def toggle_active(session: AsyncSession, bot: ManagedBot) -> None:
    bot.is_active = not bot.is_active
    await session.commit()


async def list_categories(session: AsyncSession) -> list[Category]:
    result = await session.execute(select(Category).order_by(Category.id))
    return list(result.scalars())


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.strip().lower()).strip("_")
    return slug or "category"


async def create_category(session: AsyncSession, title: str) -> Category:
    existing_codes = {category.code for category in await list_categories(session)}
    code = _slugify(title)
    if code in existing_codes:
        suffix = 2
        while f"{code}_{suffix}" in existing_codes:
            suffix += 1
        code = f"{code}_{suffix}"

    category = Category(code=code, title=title)
    session.add(category)
    await session.commit()
    return category


async def rename_category(session: AsyncSession, category: Category, title: str) -> None:
    category.title = title
    await session.commit()


async def delete_category(session: AsyncSession, category: Category) -> None:
    await session.delete(category)
    await session.commit()


async def toggle_disabled_category(session: AsyncSession, bot: ManagedBot, category_id: int) -> None:
    existing = next((dc for dc in bot.disabled_categories if dc.category_id == category_id), None)
    if existing is not None:
        bot.disabled_categories.remove(existing)
    else:
        bot.disabled_categories.append(BotDisabledCategory(category_id=category_id))
    await session.commit()


async def connect_integration(
    session: AsyncSession, bot: ManagedBot, provider: Provider, token: str
) -> None:
    existing = next((i for i in bot.integrations if i.provider == provider), None)
    if existing is not None:
        existing.encrypted_token = encrypt(token)
    else:
        bot.integrations.append(SponsorIntegration(provider=provider, encrypted_token=encrypt(token)))
        max_position = max((p.position for p in bot.priorities), default=-1)
        bot.priorities.append(ProviderPriority(provider=provider.value, position=max_position + 1))
    await session.commit()


async def move_priority(session: AsyncSession, bot: ManagedBot, provider: str, direction: int) -> None:
    ordered = sorted(bot.priorities, key=lambda p: p.position)
    index = next((i for i, p in enumerate(ordered) if p.provider == provider), None)
    if index is None:
        return
    swap_index = index + direction
    if not (0 <= swap_index < len(ordered)):
        return
    ordered[index].position, ordered[swap_index].position = (
        ordered[swap_index].position,
        ordered[index].position,
    )
    await session.commit()
