import logging
import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    api_keys: List[str]
    rate_limit_requests: int
    rate_limit_window: int


settings = Settings(
    gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
    gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
    api_keys=[
        key.strip()
        for key in os.getenv("API_KEYS", "guest-key-123,demo-key-456").split(",")
        if key.strip()
    ],
    rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "10")),
    rate_limit_window=int(os.getenv("RATE_LIMIT_WINDOW", "3600")),
)
