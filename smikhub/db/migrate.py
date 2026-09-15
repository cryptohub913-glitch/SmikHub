import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from smikhub.config import DATABASE_URL

async def run_auto_migrations():
    print("⏳ Запуск автоматических миграций базы данных...")
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)
        
        queries = [
            "ALTER TABLE bots ADD COLUMN subgram_token VARCHAR;",
            "ALTER TABLE bots ADD COLUMN flyer_token VARCHAR;",
            "ALTER TABLE bots ADD COLUMN traffy_token VARCHAR;",
            "ALTER TABLE bots ADD COLUMN piarflow_token VARCHAR;",
            "ALTER TABLE bots ADD COLUMN tgrass_token VARCHAR;"
        ]

        async with engine.begin() as conn:
            for q in queries:
                try:
                    await conn.execute(text(q))
                    print(f"✅ Выполнено: {q}")
                except Exception:
                    # Игнорируем ошибку, если колонка уже существует
                    pass
                    
        await engine.dispose()
        print("🎉 Миграции успешно завершены!")
    except Exception as e:
        print(f"⚠️ Ошибка при миграции (база может быть уже актуальна): {e}")

if __name__ == "__main__":
    asyncio.run(run_auto_migrations())