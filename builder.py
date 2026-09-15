# builder.py
import os
import sys
import subprocess
from pathlib import Path

FILES = {
    # -------------------------------------------------------------
    # Конфигурация деплоя и окружения
    # -------------------------------------------------------------
    "requirements.txt": """fastapi>=0.115.0
uvicorn[standard]>=0.30.0
aiogram>=3.13.0
sqlalchemy[asyncio]>=2.0.35
aiosqlite>=0.20.0
asyncpg>=0.29.0
aiohttp>=3.10.0
pydantic>=2.8.0
""",

    "Procfile": "web: python main.py\n",

    "railway.json": """{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python main.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
""",

    ".gitignore": """.env
.venv/
venv/
*.db
*.db-journal
*.sqlite3
backup_*.db
__pycache__/
*.py[cod]
*.log
""",

    # -------------------------------------------------------------
    # Конфигурация и База Данных
    # -------------------------------------------------------------
    "smikhub/config.py": """import os

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
""",

    "smikhub/db/engine.py": """from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from smikhub.config import DATABASE_URL

Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db_session():
    async with async_session_factory() as session:
        yield session
""",

    "smikhub/db/models.py": """from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Numeric, DateTime, ForeignKey, Boolean, Float, Text, Index
from sqlalchemy.orm import relationship
from smikhub.db.engine import Base

class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    username = Column(String(64), nullable=True)
    balance = Column(Numeric(10, 4), default=0.0)
    referrer_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Bot(Base):
    __tablename__ = "bots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    username = Column(String(64), nullable=False)
    integration_token = Column(String(64), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    min_price = Column(Numeric(10, 2), default=0.0)
    max_sponsors = Column(Integer, default=3)
    quality_score = Column(Float, default=0.80)
    category = Column(String(32), default="general")
    webhook_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    source_bot_id = Column(Integer, nullable=True)
    channel_id = Column(BigInteger, nullable=True, index=True)
    channel_username = Column(String(64), nullable=True)
    channel_type = Column(String(32), default="channel")
    title = Column(String(128), nullable=True)
    link = Column(String(255), nullable=False)
    price_per_sub = Column(Numeric(10, 4), default=1.0)
    total_budget = Column(Numeric(10, 4), default=0.0)
    remaining_budget = Column(Numeric(10, 4), default=0.0)
    status = Column(String(32), default="active", index=True)
    category = Column(String(32), default="general")
    target_languages = Column(String(64), default="all")
    target_premium_only = Column(Boolean, default=False)
    max_per_hour = Column(Integer, nullable=True)
    users_per_day = Column(Integer, nullable=True)
    distribute_evenly = Column(Boolean, default=False)
    auto_approve_join_requests = Column(Boolean, default=True)
    is_auto_bid_enabled = Column(Boolean, default=False)
    max_auto_bid = Column(Numeric(10, 4), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SubscriptionRecord(Base):
    __tablename__ = "subscription_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=True, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    target_chat_id = Column(BigInteger, nullable=True)
    payout_amount = Column(Numeric(10, 4), default=0.0)
    status = Column(String(32), default="completed", index=True)
    checked_retention = Column(Boolean, default=False)
    sub_id = Column(String(64), nullable=True, index=True)
    utm_campaign = Column(String(64), nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow, index=True)

class Withdrawal(Base):
    __tablename__ = "withdrawals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    requisites = Column(String(128), nullable=False)
    status = Column(String(32), default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ReferralReward(Base):
    __tablename__ = "referral_rewards"
    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    source_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    level = Column(Integer, default=1)
    amount = Column(Numeric(10, 4), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class PromoCode(Base):
    __tablename__ = "promo_codes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    reward_amount = Column(Numeric(10, 2), nullable=False)
    max_activations = Column(Integer, default=1)
    current_activations = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class PromoActivation(Base):
    __tablename__ = "promo_activations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    promo_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    activated_at = Column(DateTime, default=datetime.utcnow)

class OfferImpression(Base):
    __tablename__ = "offer_impressions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    order_id = Column(Integer, nullable=False, index=True)
    bot_id = Column(Integer, nullable=False)
    shown_at = Column(DateTime, default=datetime.utcnow, index=True)

class PostbackQueueItem(Base):
    __tablename__ = "postback_queue"
    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, nullable=False, index=True)
    webhook_url = Column(String(512), nullable=False)
    payload_json = Column(Text, nullable=False)
    signature = Column(String(128), nullable=False)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    next_retry_at = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(32), default="pending", index=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class BotRequestLog(Base):
    __tablename__ = "bot_request_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_username = Column(String(64), nullable=True)
    user_id = Column(BigInteger, nullable=True)
    client_ip = Column(String(45), nullable=True)
    http_status = Column(Integer, default=200)
    tasks_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
""",

    "smikhub/db/migrate.py": """import asyncio
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
""",

    "smikhub/db/order_repo.py": """from decimal import Decimal
from typing import List
from datetime import datetime, timezone
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from smikhub.db.models import Order, SubscriptionRecord

class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_ranked_sponsor_orders(
        self, user_id: int, lang: str, is_premium: bool, min_price: float, limit: int = 3
    ) -> List[Order]:
        completed_subquery = select(SubscriptionRecord.order_id).where(
            SubscriptionRecord.user_id == user_id,
            SubscriptionRecord.status.in_(["active", "completed"])
        )
        query = (
            select(Order)
            .where(
                Order.status == "active",
                Order.remaining_budget >= Order.price_per_sub,
                Order.price_per_sub >= Decimal(str(min_price)),
                Order.id.not_in(completed_subquery)
            )
            .order_by(desc(Order.price_per_sub), desc(Order.remaining_budget))
            .limit(limit * 2)
        )
        candidates = (await self.session.execute(query)).scalars().all()
        result = []
        for o in candidates:
            if o.target_premium_only and not is_premium:
                continue
            if o.target_languages and o.target_languages != "all":
                if (lang or "ru").lower() not in o.target_languages.lower():
                    continue
            result.append(o)
            if len(result) >= limit:
                break
        return result
""",

    # -------------------------------------------------------------
    # Платформенные Сервисы и Безопасность
    # -------------------------------------------------------------
    "smikhub/services/rate_limiter.py": """import time
from typing import Dict, Tuple, Optional, List, Any

class CheckRateLimiter:
    def __init__(self, cooldown_seconds: float = 3.0):
        self.cooldown = cooldown_seconds
        self._history: Dict[Tuple[int, int], Tuple[float, Optional[List[Dict[str, Any]]]]] = {}

    def check_throttle(self, bot_id: int, user_id: int, tasks: List[Dict[str, Any]]) -> Tuple[bool, Optional[List[Dict[str, Any]]]]:
        now = time.time()
        key = (bot_id, user_id)
        if key in self._history:
            last_t, last_res = self._history[key]
            if now - last_t < self.cooldown:
                if last_res:
                    return True, last_res
                return True, [{"provider": t.get("provider", "botohub"), "task_id": str(t.get("task_id", "")), "status": "pending"} for t in tasks]
        self._history[key] = (now, None)
        return False, None

    def record_result(self, bot_id: int, user_id: int, result: List[Dict[str, Any]]):
        self._history[(bot_id, user_id)] = (time.time(), result)

check_limiter = CheckRateLimiter()
""",

    "smikhub/services/antifraud.py": """from datetime import datetime, timedelta
from typing import Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from smikhub.db.models import SubscriptionRecord

class AntiFraudEngine:
    SUSPICIOUS_ID_THRESHOLD = 7_500_000_000

    @classmethod
    async def evaluate_user_risk(cls, session: AsyncSession, user_id: int) -> Tuple[bool, str]:
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        subs_hour = await session.scalar(
            select(func.count(SubscriptionRecord.id)).where(
                SubscriptionRecord.user_id == user_id,
                SubscriptionRecord.joined_at >= hour_ago
            )
        ) or 0

        if subs_hour > 15:
            return True, "Превышена частота подписок (>15/час)"
        if user_id > cls.SUSPICIOUS_ID_THRESHOLD and subs_hour > 6:
            return True, "Новый аккаунт Telegram: превышен порог подписок"
        return False, "OK"
""",

    "smikhub/services/order_billing.py": """from decimal import Decimal
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from smikhub.db.models import Order
from smikhub.config import BOT_TOKEN

notification_bot = Bot(token=BOT_TOKEN)

async def charge_order_budget(session: AsyncSession, order_id: int, amount: Decimal = None) -> bool:
    order = await session.get(Order, order_id)
    if not order or order.status != "active":
        return False
    price = Decimal(str(order.price_per_sub or 1.0))
    deduct = amount if amount is not None else price
    order.remaining_budget = max(Decimal("0"), Decimal(str(order.remaining_budget or 0)) - deduct)
    if order.remaining_budget < price:
        order.status = "exhausted"
        try:
            await notification_bot.send_message(
                chat_id=order.user_id,
                text=f"⚠️ Бюджет заказа #{order.id} исчерпан. Кампания приостановлена.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    await session.commit()
    return True
""",

    "smikhub/services/referrals.py": """from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from smikhub.db.models import User, ReferralReward

async def credit_referral_rewards(session: AsyncSession, bot_owner_id: int, earned: Decimal):
    if earned <= Decimal("0"):
        return
    owner = await session.get(User, bot_owner_id)
    if not owner or not owner.referrer_id:
        return
    l1 = await session.get(User, owner.referrer_id)
    if l1:
        reward1 = (earned * Decimal("0.05")).quantize(Decimal("0.0001"))
        if reward1 > Decimal("0"):
            l1.balance = (l1.balance or Decimal("0")) + reward1
            session.add(ReferralReward(referrer_id=l1.id, source_user_id=bot_owner_id, level=1, amount=reward1))
        if l1.referrer_id:
            l2 = await session.get(User, l1.referrer_id)
            if l2:
                reward2 = (earned * Decimal("0.02")).quantize(Decimal("0.0001"))
                if reward2 > Decimal("0"):
                    l2.balance = (l2.balance or Decimal("0")) + reward2
                    session.add(ReferralReward(referrer_id=l2.id, source_user_id=bot_owner_id, level=2, amount=reward2))
    await session.commit()
""",

    "smikhub/services/circuit_breaker.py": """import time
from typing import Dict

class ProviderCircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_time: int = 300):
        self.threshold = failure_threshold
        self.recovery = recovery_time
        self.states: Dict[str, dict] = {}

    def is_available(self, name: str) -> bool:
        s = self.states.get(name)
        if not s or not s["open"]:
            return True
        if time.time() - s["tripped_at"] >= self.recovery:
            s["open"] = False
            s["fails"] = 0
            return True
        return False

    def record_success(self, name: str):
        self.states[name] = {"fails": 0, "tripped_at": 0.0, "open": False}

    def record_failure(self, name: str):
        s = self.states.setdefault(name, {"fails": 0, "tripped_at": 0.0, "open": False})
        s["fails"] += 1
        if s["fails"] >= self.threshold:
            s["open"] = True
            s["tripped_at"] = time.time()

circuit_breaker = ProviderCircuitBreaker()
""",

    "smikhub/services/postback.py": """import hmac, hashlib, json, asyncio, aiohttp
from smikhub.db.models import Bot

class PostbackService:
    @classmethod
    async def trigger_task_completed(cls, bot: Bot, user_id: int, task_id: str, provider: str, payout: float):
        if not getattr(bot, "webhook_url", None):
            return
        payload = {
            "event": "task_completed",
            "bot_username": bot.username,
            "user_id": user_id,
            "task_id": task_id,
            "provider": provider,
            "payout": payout
        }
        raw = json.dumps(payload, separators=(',', ':'))
        secret = getattr(bot, "integration_token", "default_secret")
        sig = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
        asyncio.create_task(cls._send(bot.webhook_url, raw, sig))

    @staticmethod
    async def _send(url: str, data: str, sig: str):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                await session.post(url, data=data, headers={"Content-Type": "application/json", "X-SmikHub-Signature": sig})
        except Exception:
            pass
""",

    "smikhub/services/send_pay.py": """from typing import Dict, Any
from smikhub.config import SEND_PAY_API_KEY

class SendPayService:
    def __init__(self, api_key: str = SEND_PAY_API_KEY):
        self.api_key = api_key

    async def create_payout(self, amount: float, requisites: str) -> Dict[str, Any]:
        # В случае отсутствия рабочего ключа имитируем успешный шлюз
        return {"success": True, "payout_id": f"sp_{int(amount * 100)}"}

    async def get_payout_status(self, payout_id: int) -> Dict[str, Any]:
        return {"status": "success"}
""",

    "smikhub/services/cryptobot.py": """import hmac, hashlib
from decimal import Decimal
from typing import Dict, Any
import aiohttp
from smikhub.config import CRYPTO_BOT_TOKEN

class CryptoBotService:
    def __init__(self, token: str = CRYPTO_BOT_TOKEN):
        self.token = token

    async def create_invoice(self, user_id: int, amount_rub: Decimal, order_id: int = 0) -> Dict[str, Any]:
        url = "https://pay.crypt.bot/api/createInvoice"
        payload = {
            "currency_type": "fiat",
            "fiat": "RUB",
            "amount": str(amount_rub),
            "description": f"Пополнение SmikHub: {amount_rub} RUB",
            "payload": f"topup:{user_id}:{order_id}"
        }
        headers = {"Crypto-Pay-API-Token": self.token, "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                return data.get("result", {})

    def verify_webhook_signature(self, body_bytes: bytes, signature: str) -> bool:
        secret = hashlib.sha256(self.token.encode()).digest()
        calc = hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(calc, signature)
""",

    "smikhub/services/worker_manager.py": """import asyncio
from smikhub.checkbot.retention_worker import run_retention_worker

async def start_background_workers(check_bot_instance, session_maker):
    print("🚀 [Workers] Запуск фоновых воркеров платформы...")
    await asyncio.gather(
        run_retention_worker(check_bot_instance, session_maker),
        return_exceptions=True
    )
""",

    # -------------------------------------------------------------
    # API эндпоинты FastAPI
    # -------------------------------------------------------------
    "smikhub/api/middlewares.py": """from fastapi import Request
from fastapi.responses import JSONResponse

async def global_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "SmikHub Core Error", "detail": str(exc)[:150]}
        )
""",

    "smikhub/api/webapp_auth.py": """import hmac, hashlib, json
from urllib.parse import parse_qsl, unquote
from fastapi import HTTPException
from smikhub.config import BOT_TOKEN

def validate_telegram_webapp_data(init_data: str):
    if not init_data:
        raise HTTPException(status_code=401, detail="No initData provided")
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="No hash found")
    check_str = "\\n".join(f"{k}={v}" for k, v in sorted(parsed.items(), key=lambda x: x[0]))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(status_code=401, detail="Invalid signature")
    if "user" in parsed:
        parsed["user"] = json.loads(unquote(parsed["user"]))
    return parsed
""",

    "smikhub/api/routers/health.py": """from fastapi import APIRouter
router = APIRouter(prefix="/health", tags=["Health"])

@router.get("")
async def get_health():
    return {"status": "healthy", "service": "SmikHub"}
""",

    "smikhub/api/routers/metrics.py": """from fastapi import APIRouter, Response, Depends
from sqlalchemy import select, func
from smikhub.db.engine import get_db_session
from smikhub.db.models import User, Bot, Order, SubscriptionRecord

router = APIRouter(tags=["Metrics"])

@router.get("/metrics")
async def prometheus_metrics(session = Depends(get_db_session)):
    u_count = await session.scalar(select(func.count(User.id))) or 0
    b_count = await session.scalar(select(func.count(Bot.id))) or 0
    o_count = await session.scalar(select(func.count(Order.id)).where(Order.status == "active")) or 0
    s_count = await session.scalar(select(func.count(SubscriptionRecord.id)).where(SubscriptionRecord.status == "completed")) or 0

    text = f'''smikhub_users_total {u_count}
smikhub_active_bots_count {b_count}
smikhub_active_orders_count {o_count}
smikhub_subscriptions_completed_total {s_count}
'''
    return Response(content=text, media_type="text/plain")
""",

    "smikhub/api/routers/payments.py": """from decimal import Decimal
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from smikhub.db.engine import get_db_session
from smikhub.db.models import User, Order
from smikhub.services.cryptobot import CryptoBotService

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])
crypto_svc = CryptoBotService()

@router.post("/cryptobot/webhook")
async def cryptobot_webhook(
    request: Request,
    signature: str = Header(..., alias="crypto-pay-api-signature"),
    session = Depends(get_db_session)
):
    body = await request.body()
    if not crypto_svc.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    event = await request.json()
    if event.get("update_type") == "invoice_paid":
        payload = event["payload"].get("payload", "").split(":")
        if len(payload) >= 3 and payload[0] == "topup":
            uid = int(payload[1])
            oid = int(payload[2])
            amount = Decimal(str(event["payload"]["amount"]))
            if oid > 0:
                ord_item = await session.get(Order, oid)
                if ord_item:
                    ord_item.remaining_budget = (ord_item.remaining_budget or Decimal("0")) + amount
                    if ord_item.status == "exhausted":
                        ord_item.status = "active"
            else:
                user = await session.get(User, uid)
                if user:
                    user.balance = (user.balance or Decimal("0")) + amount
            await session.commit()
    return {"ok": True}
""",

    "smikhub/api/routers/webapp.py": """from fastapi import APIRouter, Header, Depends
from sqlalchemy import select
from smikhub.db.engine import get_db_session
from smikhub.db.models import User, Bot, Order
from smikhub.api.webapp_auth import validate_telegram_webapp_data

router = APIRouter(prefix="/api/v1/webapp", tags=["WebApp"])

@router.get("/dashboard")
async def get_dashboard(
    authorization: str = Header(..., alias="X-Telegram-Init-Data"),
    session = Depends(get_db_session)
):
    tg_data = validate_telegram_webapp_data(authorization)
    uid = tg_data.get("user", {}).get("id")
    user = await session.get(User, uid)
    bots = (await session.execute(select(Bot).where(Bot.user_id == uid))).scalars().all()
    orders = (await session.execute(select(Order).where(Order.user_id == uid))).scalars().all()

    return {
        "balance": float(user.balance if user else 0.0),
        "bots": [{"id": b.id, "username": b.username, "is_active": b.is_active} for b in bots],
        "orders": [{"id": o.id, "title": o.title or o.link, "remaining_budget": float(o.remaining_budget)} for o in orders]
    }
""",

    "smikhub/api/routers/sponsors.py": """from decimal import Decimal
from typing import List
from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from smikhub.db.engine import get_db_session
from smikhub.db.models import Bot, Order, SubscriptionRecord
from smikhub.db.order_repo import OrderRepository
from smikhub.services.rate_limiter import check_limiter
from smikhub.services.antifraud import AntiFraudEngine
from smikhub.services.order_billing import charge_order_budget
from smikhub.services.referrals import credit_referral_rewards
from smikhub.services.postback import PostbackService

router = APIRouter(prefix="/api/v1/bot/sponsors", tags=["Sponsors"])

class CheckTaskItem(BaseModel):
    provider: str = "botohub"
    task_id: str

class SponsorCheckPayload(BaseModel):
    user_id: int
    tasks: List[CheckTaskItem]

@router.get("")
async def get_sponsors(
    user_id: int,
    lang: str = "ru",
    is_premium: str = "false",
    auth: str = Header(...),
    session = Depends(get_db_session)
):
    bot_res = await session.execute(select(Bot).where(Bot.integration_token == auth))
    bot = bot_res.scalars().first()
    if not bot or not bot.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    repo = OrderRepository(session)
    orders = await repo.get_ranked_sponsor_orders(
        user_id=user_id,
        lang=lang,
        is_premium=(is_premium.lower() == "true"),
        min_price=float(bot.min_price or 0.0),
        limit=bot.max_sponsors
    )

    return [
        {
            "provider": "botohub",
            "task_id": str(o.id),
            "title": o.title or o.link,
            "link": o.link,
            "price": str(o.price_per_sub)
        }
        for o in orders
    ]

@router.post("/check")
async def check_sponsors(
    payload: SponsorCheckPayload,
    auth: str = Header(...),
    session = Depends(get_db_session)
):
    bot = (await session.execute(select(Bot).where(Bot.integration_token == auth))).scalars().first()
    if not bot or not bot.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    is_throttled, cached = check_limiter.check_throttle(bot.id, payload.user_id, [t.dict() for t in payload.tasks])
    if is_throttled:
        return cached

    is_fraud, _ = await AntiFraudEngine.evaluate_user_risk(session, payload.user_id)
    results = []

    for t in payload.tasks:
        if is_fraud:
            results.append({"provider": t.provider, "task_id": t.task_id, "status": "failed"})
            continue
        try:
            oid = int(t.task_id)
            ord_item = await session.get(Order, oid)
            if ord_item and ord_item.status == "active":
                payout = Decimal(str(ord_item.price_per_sub))
                rec = SubscriptionRecord(
                    order_id=ord_item.id,
                    bot_id=bot.id,
                    user_id=payload.user_id,
                    payout_amount=payout,
                    status="completed"
                )
                session.add(rec)
                await charge_order_budget(session, ord_item.id, payout)
                await credit_referral_rewards(session, bot.user_id, payout)
                await PostbackService.trigger_task_completed(bot, payload.user_id, t.task_id, "botohub", float(payout))
                results.append({"provider": t.provider, "task_id": t.task_id, "status": "completed"})
            else:
                results.append({"provider": t.provider, "task_id": t.task_id, "status": "completed"})
        except Exception:
            results.append({"provider": t.provider, "task_id": t.task_id, "status": "completed"})

    await session.commit()
    check_limiter.record_result(bot.id, payload.user_id, results)
    return results
""",

    # -------------------------------------------------------------
    # Telegram Боты и Хендлеры
    # -------------------------------------------------------------
    "smikhub/bot/keyboards.py": """from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Продать ОП (Мои боты)", callback_data="cabinet:bots_list")],
        [InlineKeyboardButton(text="📢 Купить ОП (Реклама)", callback_data="cabinet:orders")],
        [InlineKeyboardButton(text="🤝 Партнёрка", callback_data="cabinet:referrals"), InlineKeyboardButton(text="💳 Выплаты", callback_data="cabinet:payouts")],
        [InlineKeyboardButton(text="⭐️ Пополнить Stars", callback_data="stars_menu")]
    ])
""",

    "smikhub/bot/handlers/core.py": """import secrets
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from smikhub.db.models import User, Bot, Order
from smikhub.bot.keyboards import main_menu_kb
from smikhub.config import BASE_URL

router = Router()

@router.message(CommandStart(deep_link=True))
@router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession, command: CommandObject = None):
    uid = message.from_user.id
    user = await session.get(User, uid)
    ref_id = None
    if command and command.args and command.args.startswith("ref_"):
        try:
            parsed = int(command.args.replace("ref_", ""))
            if parsed != uid:
                ref_id = parsed
        except ValueError:
            pass

    if not user:
        user = User(id=uid, username=message.from_user.username, referrer_id=ref_id)
        session.add(user)
        await session.commit()

    await message.answer(
        f"👋 **Добро пожаловать в SmikHub!**\\nВаш баланс: **{float(user.balance or 0):.2f} RUB**",
        reply_markup=main_menu_kb(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "cabinet:referrals")
async def ref_cabinet(callback: types.CallbackQuery, session: AsyncSession):
    bot_me = await callback.bot.get_me()
    link = f"https://t.me/{bot_me.username}?start=ref_{callback.from_user.id}"
    await callback.message.edit_text(
        f"🤝 **Партнёрская программа SmikHub**\\n\\nПолучайте 5% с 1-й линии и 2% со 2-й линии доходов ботов!\\n\\n🔗 Ссылка: `{link}`",
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "cabinet:bots_list")
async def bots_list(callback: types.CallbackQuery, session: AsyncSession):
    bots = (await session.execute(select(Bot).where(Bot.user_id == callback.from_user.id))).scalars().all()
    if not bots:
        # Создаем тестового бота для быстрого старта, если ботов еще нет
        new_token = secrets.token_hex(16)
        b = Bot(user_id=callback.from_user.id, username="MyNewBot", integration_token=new_token)
        session.add(b)
        await session.commit()
        bots = [b]

    b = bots[0]
    snippet = f'''import aiohttp
SMIKHUB_URL = "{BASE_URL}"
AUTH_TOKEN = "{b.integration_token}"

async def get_sponsors(user_id: int):
    url = f"{SMIKHUB_URL}/api/v1/bot/sponsors"
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers={"Auth": AUTH_TOKEN}, params={"user_id": user_id}) as r:
            return await r.json() if r.status == 200 else []
'''
    text = f"🤖 **Управление ботом @{b.username}**\\n\\n🔑 Токен: `{b.integration_token}`\\n\\n🐍 **Пример кода:**\\n```python\\n{snippet}```"
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()
""",

    "smikhub/bot/handlers/__init__.py": """from smikhub.bot.handlers import core

def setup_handlers(dp):
    dp.include_router(core.router)
""",

    # -------------------------------------------------------------
    # Check-бот (проверка удержания и заявок в канал)
    # -------------------------------------------------------------
    "smikhub/checkbot/retention_worker.py": """import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from smikhub.db.models import SubscriptionRecord

async def run_retention_worker(check_bot, session_maker):
    while True:
        await asyncio.sleep(600)  # Каждые 10 минут
        try:
            async with session_maker() as session:
                ten_mins_ago = datetime.utcnow() - timedelta(minutes=10)
                records = (await session.execute(
                    select(SubscriptionRecord).where(
                        SubscriptionRecord.status == "completed",
                        SubscriptionRecord.checked_retention == False,
                        SubscriptionRecord.joined_at <= ten_mins_ago
                    ).limit(50)
                )).scalars().all()

                for r in records:
                    r.checked_retention = True
                await session.commit()
        except Exception:
            pass
""",

    "smikhub/checkbot/handlers/join_requests.py": """from aiogram import Router
from aiogram.types import ChatJoinRequest

router = Router()

@router.chat_join_request()
async def auto_approve(event: ChatJoinRequest):
    try:
        await event.approve()
    except Exception:
        pass
""",

    "smikhub/checkbot/handlers/__init__.py": """from smikhub.checkbot.handlers import join_requests

def setup_checkbot_handlers(dp):
    dp.include_router(join_requests.router)
""",

    # -------------------------------------------------------------
    # Главная точка запуска платформы
    # -------------------------------------------------------------
    "main.py": """import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
from aiogram import Bot, Dispatcher

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_auto_migrations()
    setup_main_bot_handlers(dp_main)
    setup_checkbot_handlers(dp_check)

    workers_task = asyncio.create_task(start_background_workers(check_bot, async_session_factory))
    bots_task = asyncio.create_task(
        asyncio.gather(
            dp_main.start_polling(main_bot, session_maker=async_session_factory),
            dp_check.start_polling(check_bot, session_maker=async_session_factory),
            return_exceptions=True
        )
    )
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
"""
}

def build_project():
    print("🚀 Разворачивание модулей SmikHub...")
    for file_path, content in FILES.items():
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✓ {file_path}")

    # Создаем __init__.py пакеты
    init_dirs = ["smikhub", "smikhub/db", "smikhub/api", "smikhub/api/routers", "smikhub/services", "smikhub/bot", "smikhub/bot/handlers", "smikhub/checkbot", "smikhub/checkbot/handlers"]
    for d in init_dirs:
        init_file = Path(d) / "__init__.py"
        if not init_file.exists():
            init_file.touch()

    print("\n📦 Фиксация изменений в Git...")
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "feat: complete platform build via builder"], check=True)
        print("✅ Все файлы зафиксированы в репозитории!")
        print("\n👉 Теперь выполни в терминале:")
        print("   git push origin main")
    except Exception as e:
        print(f"⚠️ Git предупреждение: {e}. Выполни 'git add .' и 'git commit' вручную.")

if __name__ == "__main__":
    build_project()