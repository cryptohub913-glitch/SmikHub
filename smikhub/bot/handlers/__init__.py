from smikhub.bot.handlers import core

def setup_handlers(dp):
    dp.include_router(core.router)
