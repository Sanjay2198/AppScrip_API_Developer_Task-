import logging
import os
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str
    api_keys: List[str]
    rate_limit_requests: int
    rate_limit_window: int


settings = Settings(
    openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
    api_keys=[
        key.strip()
        for key in os.getenv("API_KEYS", "guest-key-123,demo-key-456").split(",")
        if key.strip()
    ],
    rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "10")),
    rate_limit_window=int(os.getenv("RATE_LIMIT_WINDOW", "3600")),
)
