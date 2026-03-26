from fastapi import Header, HTTPException, status
from config import API_KEYS


def verify_api_key(x_api_key: str = Header(..., description="Your API key")):
    if x_api_key not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Pass it as X-Api-Key header."
        )
    return x_api_key
