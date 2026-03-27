import logging
from typing import Any, Dict
from fastapi import Depends, FastAPI, HTTPException, Path, Request
from fastapi.responses import JSONResponse
from ai_analyzer import AnalysisServiceError, build_fallback_report, generate_market_report
from auth import verify_api_key
from data_collector import collect_market_news
from rate_limiter import rate_limiter
from schemas import AnalysisResponse, ErrorResponse
from session_store import session_store
from utils import utc_now_iso, validate_sector_name

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Trade Opportunities API",
    version="1.0.0",
    description="""
## Overview
Submit an Indian sector name to get a Markdown trade report powered by Google News and Gemini AI.

## Authentication
Pass your key in the `X-Api-Key` header. Demo key: `guest-key-123` `demo-key-456`
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
    requests_remaining = rate_limiter.check(api_key)
    session_id = session_store.start_session(api_key=api_key, sector=sector, path=str(request.url.path))
    logger.info("[%s] Analyzing sector '%s'", session_id, sector)

    try:
        news_items = await collect_market_news(sector)
        session_store.record_news_count(session_id, len(news_items))
        logger.info("[%s] Collected %s news items", session_id, len(news_items))

        report_source = "gemini"
        try:
            report = await generate_market_report(sector, news_items)
        except AnalysisServiceError as exc:
            report_source = "fallback"
            logger.warning("[%s] Gemini failed, using fallback report: %s", session_id, exc.message)
            report = build_fallback_report(sector, news_items, exc.message)

        session_store.complete_session(session_id, report_source=report_source)
        return AnalysisResponse(
            session_id=session_id,
            sector=sector,
            generated_at=utc_now_iso(),
            requests_remaining=requests_remaining,
            report=report,
        )
    except HTTPException:
        session_store.fail_session(session_id)
        raise
    except Exception as exc:
        session_store.fail_session(session_id)
        logger.exception("[%s] Unexpected error", session_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/sessions", tags=["Sessions"], summary="List your sessions")
async def list_sessions(api_key: str = Depends(verify_api_key)) -> Dict[str, Any]:
    return session_store.list_for_key(api_key)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Unexpected error."})
