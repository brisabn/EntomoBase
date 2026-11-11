import math
import threading
import time


# counts failures per key inside a time window and tells when the key is blocked
# the counter lives in the process memory: it resets with the API and is not shared between processes
class AttemptLimiter:
    def __init__(self, max_attempts: int, window_seconds: int, clock=time.monotonic):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._clock = clock
        self._failures: dict = {}
        self._lock = threading.Lock()

    def _recent(self, key, now: float) -> list:
        recent = [t for t in self._failures.get(key, []) if now - t < self.window]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    # seconds until the key may try again; 0 when it is not blocked
    def seconds_remaining(self, key) -> int:
        with self._lock:
            now = self._clock()
            recent = self._recent(key, now)
            if len(recent) < self.max_attempts:
                return 0
            return max(1, math.ceil(recent[0] + self.window - now))

    def record_failure(self, key) -> None:
        with self._lock:
            now = self._clock()
            self._recent(key, now)
            self._failures.setdefault(key, []).append(now)
            # keeps the dictionary from growing forever with old keys
            if len(self._failures) > 10000:
                for other in list(self._failures):
                    self._recent(other, now)

    def reset(self, key) -> None:
        with self._lock:
            self._failures.pop(key, None)
