import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

_TEST_DB_PATH = Path(tempfile.gettempdir()) / "smikhub_test.db"
_TEST_DB_PATH.unlink(missing_ok=True)

TEST_OWNER_ID = 111222333
TEST_ADMIN_ID = 999888777
TEST_SEND_API_TOKEN = "test-send-api-token"

os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN")
os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TEST_DB_PATH}")
os.environ.setdefault("ADMIN_USER_IDS", str(TEST_ADMIN_ID))
os.environ.setdefault("SEND_API_TOKEN", TEST_SEND_API_TOKEN)

import pytest_asyncio  # noqa: E402

from smikhub.db.engine import get_engine, get_session_factory, init_models  # noqa: E402
from smikhub.db.models import Base  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _clean_database():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await init_models()
    yield


@pytest_asyncio.fixture
async def session():
    async with get_session_factory()() as db_session:
        yield db_session
