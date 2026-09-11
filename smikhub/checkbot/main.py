import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from smikhub.checkbot.handlers import router
from smikhub.config import get_settings
from smikhub.db.engine import init_models


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if settings.check_bot_token is None:
        raise RuntimeError("CHECK_BOT_TOKEN не задан в .env — check-бот не может быть запущен")

    await init_models()

    bot = Bot(token=settings.check_bot_token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
