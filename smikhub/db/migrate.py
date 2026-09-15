import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from smikhub.config import DATABASE_URL

async def fix_database():
    print(f"Подключение к базе данных...")
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    queries = [
        "ALTER TABLE bots ADD COLUMN IF NOT EXISTS subgram_token VARCHAR;",
        "ALTER TABLE bots ADD COLUMN IF NOT EXISTS flyer_token VARCHAR;",
        "ALTER TABLE bots ADD COLUMN IF NOT EXISTS traffy_token VARCHAR;",
        "ALTER TABLE bots ADD COLUMN IF NOT EXISTS piarflow_token VARCHAR;",
        "ALTER TABLE bots ADD COLUMN IF NOT EXISTS tgrass_token VARCHAR;"
    ]

    async with engine.begin() as conn:
        for q in queries:
            try:
                await conn.execute(text(q))
                print(f"✅ Успешно выполнено: {q}")
            except Exception as e:
                print(f"⚠️ Пропущено / уже существует: {e}")
                
    await engine.dispose()
    print("🎉 Миграция базы данных успешно завершена!")

if __name__ == "__main__":
    asyncio.run(fix_database())