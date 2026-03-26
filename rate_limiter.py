import time
from collections import defaultdict
from fastapi import HTTPException, status
from config import RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW

# In-memory store: { api_key: [timestamp, timestamp, ...] }
_request_log: dict = defaultdict(list)


def check_rate_limit(api_key: str):
    now = time.time()

    # Remove timestamps outside the current window
    _request_log[api_key] = [
        t for t in _request_log[api_key]
        if now - t < RATE_LIMIT_WINDOW
    ]

    if len(_request_log[api_key]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per hour."
        )

    _request_log[api_key].append(now)


def get_remaining_requests(api_key: str) -> int:
    now = time.time()
    recent = [t for t in _request_log[api_key] if now - t < RATE_LIMIT_WINDOW]
    return max(0, RATE_LIMIT_REQUESTS - len(recent))
