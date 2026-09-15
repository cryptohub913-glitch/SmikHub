import asyncio
from sqlalchemy import text
from smikhub.db.engine import engine, Base
import smikhub.db.models

SCHEMA_UPDATES = [
    ("users", "referrer_id", "BIGINT NULL"),
    ("bots", "quality_score", "FLOAT DEFAULT 0.80"),
    ("bots", "webhook_url", "VARCHAR(512) NULL"),
    ("orders", "category", "VARCHAR(32) DEFAULT 'general'"),
    ("orders", "target_languages", "VARCHAR(64) DEFAULT 'all'"),
    ("orders", "max_per_hour", "INTEGER NULL"),
    ("orders", "is_auto_bid_enabled", "BOOLEAN DEFAULT FALSE"),
    ("orders", "max_auto_bid", "NUMERIC(10, 4) NULL"),
    ("subscription_records", "sub_id", "VARCHAR(64) NULL"),
    ("subscription_records", "utm_campaign", "VARCHAR(64) NULL"),
]

async def run_auto_migrations():
    print("📦 [DB Migration] Проверка схемы...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for table, col, ctype in SCHEMA_UPDATES:
            try:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ctype};"))
            except Exception:
                pass
    print("✅ [DB Migration] База данных готова.")
