import secrets
from fastapi import Header, HTTPException
from config import settings


def verify_api_key(
    x_api_key: str = Header(..., alias="x-api-key", description="Your API key"),
) -> str:
    if not any(secrets.compare_digest(x_api_key, allowed) for allowed in settings.api_keys):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return x_api_key
