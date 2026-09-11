import enum
from datetime import datetime, timezone

from sqlalchemy import BigInteger, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CategoryMode(str, enum.Enum):
    ALL_EXCEPT_OWN = "all_except_own"
    ONLY_OWN = "only_own"


class Provider(str, enum.Enum):
    SUBGRAM = "subgram"
    FLYER = "flyer"
    TGRASS = "tgrass"
    PIARFLOW = "piarflow"


class TrafficType(str, enum.Enum):
    SUBSCRIPTIONS = "subscriptions"
    VIEWS = "views"


class DestinationType(str, enum.Enum):
    CHANNEL_CHAT = "channel_chat"
    BOT = "bot"
    RESOURCE = "resource"


class OrderStatus(str, enum.Enum):
    PAUSED = "paused"
    RUNNING = "running"


class Gender(str, enum.Enum):
    ANY = "any"
    MALE = "male"
    FEMALE = "female"


class AgeGroup(str, enum.Enum):
    ANY = "any"
    UNDER_13 = "under_13"
    AGE_14_17 = "age_14_17"
    ADULT = "adult"


class PremiumFilter(str, enum.Enum):
    NOT_IMPORTANT = "not_important"
    ONLY_PREMIUM = "only_premium"


class DepositStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"


class WithdrawalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user id
    balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    is_banned: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    bots: Mapped[list["ManagedBot"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    orders: Mapped[list["Order"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class ManagedBot(Base):
    __tablename__ = "managed_bots"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    telegram_bot_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str] = mapped_column(String(64))
    encrypted_token: Mapped[str] = mapped_column(String(255))

    is_active: Mapped[bool] = mapped_column(default=True)
    category_mode: Mapped[CategoryMode] = mapped_column(default=CategoryMode.ALL_EXCEPT_OWN)
    min_price: Mapped[float] = mapped_column(Numeric(3, 1), default=0.0)
    max_sponsors: Mapped[int] = mapped_column(default=3)

    integration_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    integration_token_encrypted: Mapped[str] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    owner: Mapped["User"] = relationship(back_populates="bots")
    disabled_categories: Mapped[list["BotDisabledCategory"]] = relationship(
        back_populates="bot", cascade="all, delete-orphan"
    )
    integrations: Mapped[list["SponsorIntegration"]] = relationship(
        back_populates="bot", cascade="all, delete-orphan"
    )
    priorities: Mapped[list["ProviderPriority"]] = relationship(
        back_populates="bot", cascade="all, delete-orphan", order_by="ProviderPriority.position"
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(64))


class BotDisabledCategory(Base):
    __tablename__ = "bot_disabled_categories"
    __table_args__ = (UniqueConstraint("bot_id", "category_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("managed_bots.id", ondelete="CASCADE"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))

    bot: Mapped["ManagedBot"] = relationship(back_populates="disabled_categories")
    category: Mapped["Category"] = relationship()


class SponsorIntegration(Base):
    __tablename__ = "sponsor_integrations"
    __table_args__ = (UniqueConstraint("bot_id", "provider"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("managed_bots.id", ondelete="CASCADE"))
    provider: Mapped[Provider] = mapped_column()
    encrypted_token: Mapped[str] = mapped_column(String(255))
    connected_at: Mapped[datetime] = mapped_column(default=_utcnow)

    bot: Mapped["ManagedBot"] = relationship(back_populates="integrations")


class ProviderPriority(Base):
    __tablename__ = "provider_priorities"
    __table_args__ = (UniqueConstraint("bot_id", "provider"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("managed_bots.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32))
    position: Mapped[int] = mapped_column()

    bot: Mapped["ManagedBot"] = relationship(back_populates="priorities")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    traffic_type: Mapped[TrafficType] = mapped_column()
    destination_type: Mapped[DestinationType] = mapped_column()
    destination_link: Mapped[str] = mapped_column(String(255))
    # Заполняется после того, как check-бот подтвердит админ-доступ к чату/каналу.
    target_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    status: Mapped[OrderStatus] = mapped_column(default=OrderStatus.PAUSED)
    price: Mapped[float] = mapped_column(Numeric(3, 2))
    spent: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    users_per_day: Mapped[int | None] = mapped_column(nullable=True)
    users_total: Mapped[int | None] = mapped_column(nullable=True)
    distribute_during_day: Mapped[bool] = mapped_column(default=False)

    gender: Mapped[Gender] = mapped_column(default=Gender.ANY)
    age_group: Mapped[AgeGroup] = mapped_column(default=AgeGroup.ANY)
    premium_filter: Mapped[PremiumFilter] = mapped_column(default=PremiumFilter.NOT_IMPORTANT)

    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    owner: Mapped["User"] = relationship(back_populates="orders")
    excluded_categories: Mapped[list["OrderExcludedCategory"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    excluded_languages: Mapped[list["OrderExcludedLanguage"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    excluded_countries: Mapped[list["OrderExcludedCountry"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    join_events: Mapped[list["OrderJoinEvent"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderExcludedCategory(Base):
    __tablename__ = "order_excluded_categories"
    __table_args__ = (UniqueConstraint("order_id", "category_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))

    order: Mapped["Order"] = relationship(back_populates="excluded_categories")
    category: Mapped["Category"] = relationship()


class OrderExcludedLanguage(Base):
    __tablename__ = "order_excluded_languages"
    __table_args__ = (UniqueConstraint("order_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(8))

    order: Mapped["Order"] = relationship(back_populates="excluded_languages")


class OrderExcludedCountry(Base):
    __tablename__ = "order_excluded_countries"
    __table_args__ = (UniqueConstraint("order_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(8))

    order: Mapped["Order"] = relationship(back_populates="excluded_countries")


class OrderJoinEvent(Base):
    __tablename__ = "order_join_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    telegram_user_id: Mapped[int] = mapped_column(BigInteger)
    telegram_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Сумма, реально списанная за это событие — не берём текущую order.price при показе
    # лога, т.к. цена заказа могла измениться после того, как событие уже оплачено.
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    joined_at: Mapped[datetime] = mapped_column(default=_utcnow)
    left_at: Mapped[datetime | None] = mapped_column(nullable=True)

    order: Mapped["Order"] = relationship(back_populates="join_events")


class PlatformSettings(Base):
    """Единственная строка (id=1) с глобальными настройками платформы."""

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    min_deposit_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=1)
    min_withdrawal_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=1)
    sell_ap_enabled: Mapped[bool] = mapped_column(default=True)
    buy_ap_enabled: Mapped[bool] = mapped_column(default=True)

    # Границы сетки "Мин. цена" в панели бота ("Продать ОП") и значение по умолчанию для
    # только что подключённых ботов.
    sell_price_grid_min: Mapped[float] = mapped_column(Numeric(3, 1), default=0.5)
    sell_price_grid_max: Mapped[float] = mapped_column(Numeric(3, 1), default=3.0)
    sell_default_min_price: Mapped[float] = mapped_column(Numeric(3, 1), default=0.0)

    # Границы сетки "Макс. спонсоров" и значение по умолчанию для новых ботов.
    sell_sponsors_grid_min: Mapped[int] = mapped_column(default=1)
    sell_sponsors_grid_max: Mapped[int] = mapped_column(default=10)
    sell_default_max_sponsors: Mapped[int] = mapped_column(default=3)

    # Границы сетки цены заказа в "Купить ОП" (сколько рекламодатель платит за
    # подписчика/показ).
    buy_price_grid_min: Mapped[float] = mapped_column(Numeric(3, 2), default=1.2)
    buy_price_grid_max: Mapped[float] = mapped_column(Numeric(3, 2), default=6.0)


class DepositInvoice(Base):
    __tablename__ = "deposit_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    send_invoice_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[DepositStatus] = mapped_column(default=DepositStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(nullable=True)


class WithdrawalRequest(Base):
    __tablename__ = "withdrawal_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[WithdrawalStatus] = mapped_column(default=WithdrawalStatus.PENDING)
    spend_id: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    decided_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
