from decimal import Decimal

from pydantic import BaseModel


class BotConfigResponse(BaseModel):
    bot_username: str
    is_active: bool
    category_mode: str
    min_price: Decimal
    max_sponsors: int
    disabled_categories: list[str]
    provider_priority: list[str]


class SponsorTaskResponse(BaseModel):
    provider: str
    task_id: str
    title: str
    link: str
    price: Decimal | None
    task_type: str


class CheckTaskItem(BaseModel):
    provider: str
    task_id: str


class CheckTasksRequest(BaseModel):
    user_id: int
    tasks: list[CheckTaskItem]


class CheckTaskResult(BaseModel):
    provider: str
    task_id: str
    status: str
