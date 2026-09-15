import hmac, hashlib, json, asyncio, aiohttp
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
