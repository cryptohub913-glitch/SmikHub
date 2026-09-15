import asyncio
from smikhub.checkbot.retention_worker import run_retention_worker

async def start_background_workers(check_bot_instance, session_maker):
    print("🚀 [Workers] Запуск фоновых воркеров платформы...")
    await asyncio.gather(
        run_retention_worker(check_bot_instance, session_maker),
        return_exceptions=True
    )
