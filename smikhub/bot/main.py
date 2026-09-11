import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from smikhub.bot.handlers import build_root_router
from smikhub.bot.middlewares import BanCheckMiddleware, DbSessionMiddleware
from smikhub.config import get_settings
from smikhub.db.engine import get_session_factory, init_models


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.middleware(DbSessionMiddleware(get_session_factory()))
    dispatcher.update.middleware(BanCheckMiddleware())
    dispatcher.include_router(build_root_router())
    return dispatcher


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    await init_models()

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = create_dispatcher()

    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
