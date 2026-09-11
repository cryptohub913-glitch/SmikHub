from aiogram import Router

from smikhub.bot.handlers import (
    add_bot,
    admin,
    bot_panel,
    buy_ap,
    cabinet,
    categories,
    delete,
    diagnostics,
    integrations,
    order_delete,
    order_log,
    order_panel,
    order_price,
    order_settings,
    order_stats,
    order_targeting,
    pricing,
    priority,
    start,
    stats,
    token,
)


def build_root_router() -> Router:
    router = Router(name="root")
    router.include_router(start.router)
    router.include_router(add_bot.router)
    router.include_router(bot_panel.router)
    router.include_router(categories.router)
    router.include_router(pricing.router)
    router.include_router(integrations.router)
    router.include_router(priority.router)
    router.include_router(token.router)
    router.include_router(stats.router)
    router.include_router(diagnostics.router)
    router.include_router(delete.router)
    router.include_router(buy_ap.router)
    router.include_router(order_panel.router)
    router.include_router(order_price.router)
    router.include_router(order_targeting.router)
    router.include_router(order_settings.router)
    router.include_router(order_stats.router)
    router.include_router(order_log.router)
    router.include_router(order_delete.router)
    router.include_router(cabinet.router)
    router.include_router(admin.router)
    return router
