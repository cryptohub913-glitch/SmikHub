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
    print("📦 [DB Migration] Создание таблиц...", flush=True)
    # 1. Гарантированно фиксируем создание таблиц в отдельной чистой транзакции
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ [DB Migration] Таблицы успешно зафиксированы в БД.", flush=True)

    # 2. Накатываем обновления колонок изолированно через IF NOT EXISTS
    for table, col, ctype in SCHEMA_UPDATES:
        try:
            async with engine.begin() as conn:
                if engine.dialect.name == "postgresql":
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {ctype};"))
                else:
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ctype};"))
        except Exception:
            pass
    print("✅ [DB Migration] Схема базы данных актуальна.", flush=True)


if __name__ == "__main__":
    asyncio.run(run_auto_migrations())