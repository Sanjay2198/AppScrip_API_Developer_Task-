import html
import re
from datetime import datetime, timezone

from fastapi import HTTPException


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: str) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def validate_sector_name(sector: str) -> str:
    cleaned = sector.strip().lower()
    if len(cleaned) < 2 or len(cleaned) > 50:
        raise HTTPException(status_code=400, detail="Sector must be 2-50 characters.")
    if not cleaned.replace("-", "").replace(" ", "").isalpha():
        raise HTTPException(
            status_code=400,
            detail="Sector may only contain letters, spaces, or hyphens.",
        )
    return cleaned
