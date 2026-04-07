import logging
import re
import secrets
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from analyzer import AnalysisServiceError, build_fallback_report, collect_market_news, generate_market_report
from config import settings

logger = logging.getLogger(__name__)


class AnalysisResponse(BaseModel):
    session_id: str = Field(..., examples=["abc-123"])
    sector: str = Field(..., examples=["pharmaceuticals"])
    generated_at: str = Field(..., examples=["2025-03-26T15:00:00+00:00"])
    requests_remaining: int = Field(..., examples=[9])
    report: str = Field(..., description="Full Markdown report")


class ErrorResponse(BaseModel):
    detail: str = Field(..., examples=["Invalid API key"])


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def validate_sector_name(sector: str) -> str:
    cleaned = sector.strip().lower()
    if len(cleaned) < 2 or len(cleaned) > 50:
        raise HTTPException(status_code=400, detail="Sector must be 2-50 characters.")
    if not re.fullmatch(r"[a-z\s\-]+", cleaned):
        raise HTTPException(status_code=400, detail="Sector may only contain letters, spaces, or hyphens.")
    return cleaned


def verify_api_key(x_api_key: str = Header(..., alias="x-api-key", description="Your API key")) -> str:
    if not any(secrets.compare_digest(x_api_key, k) for k in settings.api_keys):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return x_api_key


_request_log: Dict[str, List[float]] = defaultdict(list)


def check_rate_limit(api_key: str) -> int:
    now = time.time()
    recent = [t for t in _request_log[api_key] if now - t < settings.rate_limit_window]
    if len(recent) >= settings.rate_limit_requests:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Max {settings.rate_limit_requests} requests per hour.")
    recent.append(now)
    _request_log[api_key] = recent
    return settings.rate_limit_requests - len(recent)


_sessions: Dict[str, Dict[str, Any]] = {}


def start_session(api_key: str, sector: str, path: str) -> str:
    sid = str(uuid.uuid4())
    _sessions[sid] = {"api_key": api_key, "sector": sector, "started_at": utc_now_iso(), "status": "processing", "path": path}
    return sid


def complete_session(sid: str, report_source: str) -> None:
    _sessions[sid].update({"status": "completed", "completed_at": utc_now_iso(), "report_source": report_source})


def fail_session(sid: str) -> None:
    if sid in _sessions:
        _sessions[sid]["status"] = "failed"


app = FastAPI(
    title="Trade Opportunities API",
    version="1.0.0",
    description="""

## Authentication
Pass your key in the `X-Api-Key` header. Demo keys: `guest-key-123` `demo-key-456`
""",
)


@app.get("/", tags=["Info"])
async def root() -> Dict[str, str]:
    return {"message": "Trade Opportunities API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health", tags=["Info"])
async def health() -> Dict[str, str]:
    return {"status": "healthy", "timestamp": utc_now_iso()}


@app.get(
    "/analyze/{sector}",
    tags=["Analysis"],
    summary="Generate trade report for a sector",
    response_model=AnalysisResponse,
    responses={
        200: {"description": "Markdown report returned"},
        400: {"model": ErrorResponse, "description": "Bad sector name"},
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Unexpected server error"},
    },
)
async def analyze(
    request: Request,
    sector: str = Path(..., min_length=2, max_length=50, examples=["pharmaceuticals"]),
    api_key: str = Depends(verify_api_key),
) -> AnalysisResponse:
    sector = validate_sector_name(sector)
    requests_remaining = check_rate_limit(api_key)
    sid = start_session(api_key=api_key, sector=sector, path=str(request.url.path))
    logger.info("[%s] Analyzing sector '%s'", sid, sector)

    try:
        news_items = await collect_market_news(sector)
        _sessions[sid]["news_items"] = len(news_items)
        logger.info("[%s] Collected %s news items", sid, len(news_items))

        report_source = "gemini"
        try:
            report = await generate_market_report(sector, news_items)
        except AnalysisServiceError as exc:
            report_source = "fallback"
            logger.warning("[%s] AI failed, using fallback: %s", sid, exc.message)
            report = build_fallback_report(sector, news_items, exc.message)

        complete_session(sid, report_source=report_source)
        return AnalysisResponse(
            session_id=sid,
            sector=sector,
            generated_at=utc_now_iso(),
            requests_remaining=requests_remaining,
            report=report,
        )
    except HTTPException:
        fail_session(sid)
        raise
    except Exception as exc:
        fail_session(sid)
        logger.exception("[%s] Unexpected error", sid)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/sessions", tags=["Sessions"], summary="List your sessions")
async def sessions(api_key: str = Depends(verify_api_key)) -> Dict[str, Any]:
    mine = {
        sid: {k: v for k, v in data.items() if k != "api_key"}
        for sid, data in _sessions.items()
        if data.get("api_key") == api_key
    }
    return {"count": len(mine), "sessions": mine}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Unexpected error."})
