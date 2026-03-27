import time
from collections import defaultdict
from typing import DefaultDict, List
from fastapi import HTTPException
from config import settings


class RateLimiter:
    def __init__(self) -> None:
        self._request_log: DefaultDict[str, List[float]] = defaultdict(list)

    def check(self, api_key: str) -> int:
        now = time.time()
        recent = [
            timestamp
            for timestamp in self._request_log[api_key]
            if now - timestamp < settings.rate_limit_window
        ]
        if len(recent) >= settings.rate_limit_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {settings.rate_limit_requests} requests per hour.",
            )

        recent.append(now)
        self._request_log[api_key] = recent
        return settings.rate_limit_requests - len(recent)


rate_limiter = RateLimiter()
