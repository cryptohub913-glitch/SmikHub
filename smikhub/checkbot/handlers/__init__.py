from smikhub.checkbot.handlers import join_requests

def setup_checkbot_handlers(dp):
    dp.include_router(join_requests.router)
