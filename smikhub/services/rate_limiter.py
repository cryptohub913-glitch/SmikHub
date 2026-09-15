import time
from typing import Dict, Tuple, Optional, List, Any

class CheckRateLimiter:
    def __init__(self, cooldown_seconds: float = 3.0):
        self.cooldown = cooldown_seconds
        self._history: Dict[Tuple[int, int], Tuple[float, Optional[List[Dict[str, Any]]]]] = {}

    def check_throttle(self, bot_id: int, user_id: int, tasks: List[Dict[str, Any]]) -> Tuple[bool, Optional[List[Dict[str, Any]]]]:
        now = time.time()
        key = (bot_id, user_id)
        if key in self._history:
            last_t, last_res = self._history[key]
            if now - last_t < self.cooldown:
                if last_res:
                    return True, last_res
                return True, [{"provider": t.get("provider", "botohub"), "task_id": str(t.get("task_id", "")), "status": "pending"} for t in tasks]
        self._history[key] = (now, None)
        return False, None

    def record_result(self, bot_id: int, user_id: int, result: List[Dict[str, Any]]):
        self._history[(bot_id, user_id)] = (time.time(), result)

check_limiter = CheckRateLimiter()
