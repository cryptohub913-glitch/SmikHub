import hmac, hashlib
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
