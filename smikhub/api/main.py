from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from smikhub.api.routers import config, sponsors, webhooks
from smikhub.db.engine import init_models

DESCRIPTION = (
    "Backend API SmikHub. Отдаёт конфигурацию подключённого бота по токену интеграции, "
    "выдаёт реальные спонсорские задачи из подключённых сетей (Flyer/Tgrass/PiarFlow — "
    "Subgram пока не реализован, нет документации API) через /api/v1/bot/sponsors и "
    "принимает вебхуки Send Crypto Pay для пополнений баланса. Нативный инвентарь "
    "спонсоров из «Купить ОП» в выдаче пока не участвует — это отдельная, ещё не "
    "реализованная задача."
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_models()
    yield


app = FastAPI(title="SmikHub API", description=DESCRIPTION, lifespan=lifespan)
app.include_router(config.router)
app.include_router(webhooks.router)
app.include_router(sponsors.router)
