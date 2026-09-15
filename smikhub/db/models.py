from datetime import datetime
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
    
    # Токены сторонних интеграций
    subgram_token = Column(String, nullable=True)
    flyer_token = Column(String, nullable=True)
    traffy_token = Column(String, nullable=True)
    piarflow_token = Column(String, nullable=True)
    tgrass_token = Column(String, nullable=True)

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

# --- ДОБАВЛЕННЫЕ НОВЫЕ ТАБЛИЦЫ ДЛЯ НАСТРОЕК И ТИКЕТОВ ---
class SystemSetting(Base):
    __tablename__ = "system_settings"
    key = Column(String(50), primary_key=True)
    value = Column(String(255), nullable=True)

class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    message = Column(Text, nullable=False)
    status = Column(String(20), default='open', index=True)
    created_at = Column(DateTime, default=datetime.utcnow)