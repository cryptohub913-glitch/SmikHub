import time
from typing import Dict

class ProviderCircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_time: int = 300):
        self.threshold = failure_threshold
        self.recovery = recovery_time
        self.states: Dict[str, dict] = {}

    def is_available(self, name: str) -> bool:
        s = self.states.get(name)
        if not s or not s["open"]:
            return True
        if time.time() - s["tripped_at"] >= self.recovery:
            s["open"] = False
            s["fails"] = 0
            return True
        return False

    def record_success(self, name: str):
        self.states[name] = {"fails": 0, "tripped_at": 0.0, "open": False}

    def record_failure(self, name: str):
        s = self.states.setdefault(name, {"fails": 0, "tripped_at": 0.0, "open": False})
        s["fails"] += 1
        if s["fails"] >= self.threshold:
            s["open"] = True
            s["tripped_at"] = time.time()

circuit_breaker = ProviderCircuitBreaker()
