from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from smikhub.config import get_settings
from smikhub.constants import CATEGORIES
from smikhub.db.models import Base, Category

_engine = create_async_engine(get_settings().database_url)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def init_models() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_categories()


async def _seed_categories() -> None:
    async with _session_factory() as session:
        existing = {row.code for row in (await session.execute(select(Category))).scalars()}
        missing = [Category(code=code, title=title) for code, title in CATEGORIES if code not in existing]
        if missing:
            session.add_all(missing)
            await session.commit()


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with _session_factory() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return _session_factory


def get_engine():
    return _engine
