import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "mock_bot_token")
CHECK_BOT_TOKEN = os.getenv("CHECK_BOT_TOKEN", "mock_check_bot_token")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///smikhub.db")

# Авто-коррекция протокола PostgreSQL для asyncpg на Railway
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN", "")
SEND_PAY_API_KEY = os.getenv("SEND_PAY_API_KEY", "")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
BASE_URL = os.getenv("BASE_URL", "https://smikhub-production.up.railway.app")
