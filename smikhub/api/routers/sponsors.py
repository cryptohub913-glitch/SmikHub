import logging
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smikhub.api.db import get_session
from smikhub.api.deps import get_authenticated_bot
from smikhub.api.schemas import CheckTaskResult, CheckTasksRequest, SponsorTaskResponse
from smikhub.constants import NATIVE_PROVIDER
from smikhub.crypto import decrypt
from smikhub.db import order_repo
from smikhub.db.models import AgeGroup, Gender, ManagedBot, Order, OrderJoinEvent, Provider
from smikhub.services.sponsor_providers import flyer, piarflow, tgrass
from smikhub.services.sponsor_providers.common import SponsorProviderError, SponsorTask

router = APIRouter(prefix="/api/v1/bot", tags=["sponsors"])
logger = logging.getLogger(__name__)

_GENDER_MAP = {
    "male": Gender.MALE,
    "m": Gender.MALE,
    "man": Gender.MALE,
    "female": Gender.FEMALE,
    "f": Gender.FEMALE,
    "woman": Gender.FEMALE,
}


def _map_tgrass_gender(raw: str | None) -> Gender | None:
    if raw is None:
        return None
    return _GENDER_MAP.get(raw.strip().lower())


def _map_tgrass_age(age: int | None) -> AgeGroup | None:
    if age is None:
        return None
    if age < 14:
        return AgeGroup.UNDER_13
    if age <= 17:
        return AgeGroup.AGE_14_17
    return AgeGroup.ADULT

_GET_TASKS = {
    Provider.FLYER: lambda token, user_id, chat_id, is_premium, lang, limit: flyer.get_tasks(
        token, user_id, limit=limit
    ),
    Provider.TGRASS: lambda token, user_id, chat_id, is_premium, lang, limit: tgrass.get_tasks(
        token, user_id, is_premium=is_premium, lang=lang, limit=limit
    ),
    Provider.PIARFLOW: lambda token, user_id, chat_id, is_premium, lang, limit: piarflow.get_tasks(
        token, user_id, chat_id, max_sponsors=limit
    ),
}

_CHECK_TASKS = {
    Provider.FLYER: lambda token, user_id, task_ids: flyer.check_tasks(token, task_ids),
    Provider.TGRASS: lambda token, user_id, task_ids: tgrass.check_tasks(token, user_id, task_ids),
    Provider.PIARFLOW: lambda token, user_id, task_ids: piarflow.check_tasks(token, user_id, task_ids),
}


def _order_to_sponsor_task(order: Order) -> SponsorTask:
    return SponsorTask(
        provider=NATIVE_PROVIDER,
        task_id=str(order.id),
        title=order.destination_link,
        link=order.destination_link,
        price=Decimal(str(order.price)),
        task_type=order.traffic_type.value,
    )


@router.get("/sponsors", response_model=list[SponsorTaskResponse])
async def get_sponsors(
    user_id: int,
    chat_id: int | None = None,
    is_premium: bool = False,
    lang: str = "ru",
    bot: ManagedBot = Depends(get_authenticated_bot),
    session: AsyncSession = Depends(get_session),
) -> list[SponsorTask]:
    effective_chat_id = chat_id if chat_id is not None else user_id
    integrations_by_provider = {integration.provider: integration for integration in bot.integrations}
    ordered_priorities = sorted(bot.priorities, key=lambda p: p.position)

    min_price = Decimal(str(bot.min_price))
    collected: list[SponsorTask] = []

    # Если у бота подключён Tgrass — используем его данные о подписчике (пол/возраст/
    # страна) для настоящего таргетинга собственных заказов botohub. Работает только для
    # пользователей, уже известных Tgrass; иначе фильтры просто не применяются, как раньше.
    tgrass_integration = integrations_by_provider.get(Provider.TGRASS)
    tgrass_gender = tgrass_age_group = tgrass_country = None
    if tgrass_integration is not None:
        try:
            profile = await tgrass.get_subscriber(decrypt(tgrass_integration.encrypted_token), user_id)
        except SponsorProviderError:
            logger.warning("tgrass subscriber lookup failed for bot %s", bot.id, exc_info=True)
            profile = None
        if profile is not None:
            tgrass_gender = _map_tgrass_gender(profile.gender)
            tgrass_age_group = _map_tgrass_age(profile.age)
            tgrass_country = profile.country

    for priority in ordered_priorities:
        if len(collected) >= bot.max_sponsors:
            break
        remaining = bot.max_sponsors - len(collected)

        if priority.provider == NATIVE_PROVIDER:
            orders = await order_repo.list_eligible_orders_for_delivery(
                session,
                is_premium,
                lang,
                remaining,
                gender=tgrass_gender,
                age_group=tgrass_age_group,
                country=tgrass_country,
            )
            tasks = [_order_to_sponsor_task(order) for order in orders]
        else:
            try:
                provider = Provider(priority.provider)
            except ValueError:
                continue  # неизвестная площадка в приоритете — пропускаем

            get_tasks = _GET_TASKS.get(provider)
            integration = integrations_by_provider.get(provider)
            if get_tasks is None or integration is None:
                continue

            try:
                tasks = await get_tasks(
                    decrypt(integration.encrypted_token), user_id, effective_chat_id, is_premium, lang, remaining
                )
            except SponsorProviderError:
                logger.warning("sponsor provider %s failed for bot %s", provider.value, bot.id, exc_info=True)
                continue

        for task in tasks:
            if task.price is not None and task.price < min_price:
                continue
            collected.append(task)
            if len(collected) >= bot.max_sponsors:
                break

    return collected


async def _check_native_tasks(session: AsyncSession, user_id: int, task_ids: list[str]) -> dict[str, str]:
    order_ids = [int(task_id) for task_id in task_ids if task_id.isdigit()]
    if not order_ids:
        return {}

    result = await session.execute(
        select(OrderJoinEvent.order_id).where(
            OrderJoinEvent.order_id.in_(order_ids),
            OrderJoinEvent.telegram_user_id == user_id,
            OrderJoinEvent.left_at.is_(None),
        )
    )
    completed_order_ids = {str(order_id) for order_id in result.scalars()}
    return {task_id: "completed" if task_id in completed_order_ids else "not_completed" for task_id in task_ids}


@router.post("/sponsors/check", response_model=list[CheckTaskResult])
async def check_sponsors(
    payload: CheckTasksRequest,
    bot: ManagedBot = Depends(get_authenticated_bot),
    session: AsyncSession = Depends(get_session),
) -> list[CheckTaskResult]:
    integrations_by_provider = {integration.provider: integration for integration in bot.integrations}

    native_task_ids: list[str] = []
    task_ids_by_provider: dict[Provider, list[str]] = {}
    for item in payload.tasks:
        if item.provider == NATIVE_PROVIDER:
            native_task_ids.append(item.task_id)
            continue
        try:
            provider = Provider(item.provider)
        except ValueError:
            continue
        task_ids_by_provider.setdefault(provider, []).append(item.task_id)

    results: list[CheckTaskResult] = []

    if native_task_ids:
        native_statuses = await _check_native_tasks(session, payload.user_id, native_task_ids)
        results.extend(
            CheckTaskResult(provider=NATIVE_PROVIDER, task_id=tid, status=native_statuses.get(tid, "unknown"))
            for tid in native_task_ids
        )

    for provider, task_ids in task_ids_by_provider.items():
        check_tasks = _CHECK_TASKS.get(provider)
        integration = integrations_by_provider.get(provider)
        if check_tasks is None or integration is None:
            results.extend(CheckTaskResult(provider=provider.value, task_id=tid, status="unknown") for tid in task_ids)
            continue

        try:
            statuses = await check_tasks(decrypt(integration.encrypted_token), payload.user_id, task_ids)
        except SponsorProviderError:
            logger.warning("sponsor provider %s check failed for bot %s", provider.value, bot.id, exc_info=True)
            statuses = {}

        for task_id in task_ids:
            results.append(
                CheckTaskResult(provider=provider.value, task_id=task_id, status=statuses.get(task_id, "unknown"))
            )

    return results
