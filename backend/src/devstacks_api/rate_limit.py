import time


class InMemoryRateLimiter:
    """Sliding-window rate limiter, per-process.

    Suitable for a single backend instance. If the backend is ever scaled
    horizontally, this needs to move to a shared store (e.g. Redis) since
    each process would otherwise enforce its own independent limit.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be at least 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        hits = [hit for hit in self._hits.get(key, []) if hit > cutoff]
        if len(hits) >= self._max_requests:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True
