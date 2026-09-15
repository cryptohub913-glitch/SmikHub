import asyncio
import logging
from typing import Callable, Dict, Any, Awaitable
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import TelegramObject

from smikhub.config import BOT_TOKEN, CHECK_BOT_TOKEN, PORT, HOST
from smikhub.db.engine import async_session_factory
from smikhub.db.migrate import run_auto_migrations
from smikhub.services.worker_manager import start_background_workers

from smikhub.bot.handlers import setup_handlers as setup_main_bot_handlers
from smikhub.checkbot.handlers import setup_checkbot_handlers

from smikhub.api.routers import sponsors, payments, health, webapp, metrics
from smikhub.api.middlewares import global_exception_middleware

logging.basicConfig(level=logging.INFO)

main_bot = Bot(token=BOT_TOKEN)
check_bot = Bot(token=CHECK_BOT_TOKEN)
dp_main = Dispatcher()
dp_check = Dispatcher()


# Автоматическая выдача и закрытие сессии БД для каждого события Telegram
class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self.session_pool() as session:
            data["session"] = session
            return await handler(event, data)


async def run_bots():
    await asyncio.gather(
        dp_main.start_polling(main_bot),
        dp_check.start_polling(check_bot),
        return_exceptions=True
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_auto_migrations()

    # Подключаем сессию БД ко всем входящим апдейтам ботов
    db_middleware = DbSessionMiddleware(async_session_factory)
    dp_main.update.outer_middleware(db_middleware)
    dp_check.update.outer_middleware(db_middleware)

    setup_main_bot_handlers(dp_main)
    setup_checkbot_handlers(dp_check)

    workers_task = asyncio.create_task(
        start_background_workers(check_bot, async_session_factory)
    )
    bots_task = asyncio.create_task(run_bots())

    yield

    workers_task.cancel()
    bots_task.cancel()
    await main_bot.session.close()
    await check_bot.session.close()


app = FastAPI(title="SmikHub", lifespan=lifespan)
app.middleware("http")(global_exception_middleware)

app.include_router(health.router)
app.include_router(sponsors.router)
app.include_router(payments.router)
app.include_router(webapp.router)
app.include_router(metrics.router)

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)