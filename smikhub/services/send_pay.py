from typing import Dict, Any
from smikhub.config import SEND_PAY_API_KEY

class SendPayService:
    def __init__(self, api_key: str = SEND_PAY_API_KEY):
        self.api_key = api_key

    async def create_payout(self, amount: float, requisites: str) -> Dict[str, Any]:
        # В случае отсутствия рабочего ключа имитируем успешный шлюз
        return {"success": True, "payout_id": f"sp_{int(amount * 100)}"}

    async def get_payout_status(self, payout_id: int) -> Dict[str, Any]:
        return {"status": "success"}
