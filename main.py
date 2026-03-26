import html
import logging
import os
import re
import time
import uuid
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
API_KEYS = [
    key.strip()
    for key in os.getenv("API_KEYS", "guest-key-123,demo-key-456").split(",")
    if key.strip()
]
RATE_LIMIT = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
RATE_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sessions: Dict[str, Dict[str, Any]] = {}
request_log: Dict[str, List[float]] = defaultdict(list)

app = FastAPI(
    title="Trade Opportunities API",
    version="1.0.0",
    description="""
## Overview
Submit an Indian sector name to get a Markdown trade report powered by Google News and Gemini AI.

## Authentication
Pass your key in the `X-Api-Key` header. Demo key: `guest-key-123`

## Rate limit
10 requests per hour per key.
""",
)


class AnalysisResponse(BaseModel):
    session_id: str = Field(..., examples=["abc-123"])
    sector: str = Field(..., examples=["pharmaceuticals"])
    generated_at: str = Field(..., examples=["2025-03-26T15:00:00+00:00"])
    requests_remaining: int = Field(..., examples=[9])
    report: str = Field(..., description="Full Markdown report")


class ErrorResponse(BaseModel):
    detail: str = Field(..., examples=["Invalid API key"])


PROMPT_TEMPLATE = """You are a trade and market analyst specializing in Indian industry sectors.

Use the recent news signals below to write a structured trade opportunities report.
Be factual, concise, and actionable. Focus on India and near-term trade implications.

RECENT NEWS SIGNALS:
{news_block}

Write the full response in Markdown with this exact structure:

# Trade Opportunities Report: {sector} Sector in India

## Executive Summary
## Current Market Overview
## Trade Opportunities
### Export Opportunities
### Import Opportunities
## Key Trends
## Investment Highlights
## Challenges & Risks
## Recommendations
## Sources
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def verify_key(
    x_api_key: str = Header(..., alias="x-api-key", description="Your API key"),
) -> str:
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return x_api_key


def check_rate(api_key: str) -> int:
    now = time.time()
    recent = [timestamp for timestamp in request_log[api_key] if now - timestamp < RATE_WINDOW]
    if len(recent) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT} requests per hour.",
        )

    recent.append(now)
    request_log[api_key] = recent
    return RATE_LIMIT - len(recent)


def clean_feed_text(value: str) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def search_news(sector: str) -> List[str]:
    current_year = datetime.now(timezone.utc).year
    queries = [
        f"{sector} India trade {current_year}",
        f"{sector} India export import market",
        f"{sector} India investment opportunities",
    ]

    items: List[str] = []
    seen = set()

    with httpx.Client(timeout=10, follow_redirects=True) as client:
        for query in queries:
            url = (
                "https://news.google.com/rss/search"
                f"?q={query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
            )
            try:
                response = client.get(url)
                response.raise_for_status()
                root = ET.fromstring(response.text)
                for item in root.findall(".//item")[:4]:
                    title = clean_feed_text(item.findtext("title", ""))
                    description = clean_feed_text(item.findtext("description", ""))
                    line = title if not description else f"{title} - {description}"
                    normalized = line.lower()
                    if line and normalized not in seen:
                        seen.add(normalized)
                        items.append(line)
            except Exception as exc:
                logger.warning("News search failed for '%s': %s", query, exc)

    return items[:9]


def build_prompt(sector: str, news_items: List[str]) -> str:
    news_block = "\n".join(f"- {item}" for item in news_items)
    if not news_block:
        news_block = "- No live Google News items were available. Use general sector knowledge and state assumptions clearly."
    return PROMPT_TEMPLATE.format(sector=sector.title(), news_block=news_block)


def extract_gemini_text(payload: Dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini returned no candidates.")

    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text = "\n".join(part.get("text", "") for part in parts if part.get("text")).strip()
    if not text:
        raise ValueError("Gemini response did not contain report text.")
    return text


def call_gemini(sector: str, news_items: List[str]) -> str:
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured.")

    payload = {
        "contents": [{"parts": [{"text": build_prompt(sector, news_items)}]}],
        "generationConfig": {"temperature": 0.3},
    }
    candidate_models = []
    for model_name in [GEMINI_MODEL, "gemini-2.5-flash", "gemini-2.0-flash"]:
        if model_name and model_name not in candidate_models:
            candidate_models.append(model_name)

    last_error = "Gemini request failed."
    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        try:
            response = httpx.post(
                url,
                json=payload,
                headers={"x-goog-api-key": GEMINI_API_KEY},
                timeout=60,
            )
        except httpx.ConnectError as exc:
            raise HTTPException(status_code=503, detail="Cannot reach Gemini. Check your network.") from exc
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="Gemini request timed out.") from exc

        if response.status_code == 404:
            last_error = f"Model '{model_name}' was not found."
            logger.warning("Gemini model '%s' was not found, trying next model.", model_name)
            continue
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Gemini rate limit hit. Try again later.")
        if response.status_code in {401, 403}:
            raise HTTPException(status_code=500, detail="Gemini API key is invalid or unauthorized.")
        if not response.is_success:
            detail = clean_feed_text(response.text)[:200] or "Unknown Gemini error."
            raise HTTPException(status_code=502, detail=f"Gemini request failed: {detail}")

        try:
            report = extract_gemini_text(response.json())
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        logger.info("Gemini report generated with model '%s'", model_name)
        return report

    raise HTTPException(status_code=502, detail=last_error)


def build_fallback_report(sector: str, news_items: List[str], reason: str) -> str:
    source_lines = "\n".join(f"- {item}" for item in news_items) or "- No live Google News items were available."

    return f"""# Trade Opportunities Report: {sector.title()} Sector in India

## Executive Summary
Gemini was unavailable for this request, so this report uses a simple headline-driven fallback summary.
The Indian {sector} sector still appears active enough to justify deeper trade and investment review.

## Current Market Overview
Recent coverage suggests ongoing movement in demand, policy, supply chains, and capital deployment tied to the {sector} sector in India.
Use the news items below as a directional signal, not as final due diligence.

## Trade Opportunities
### Export Opportunities
- Look for markets where Indian {sector} products or services have cost, scale, or compliance advantages.
- Track exporters, distributors, and policy updates that can improve access to foreign buyers.

### Import Opportunities
- Identify imported raw materials, machinery, or technology that can improve domestic capacity and margins.
- Prioritize inputs that remove bottlenecks or improve quality for Indian producers.

## Key Trends
- Policy and regulatory changes can quickly affect market access and pricing.
- Capacity expansion and supply-chain resilience remain important for trade execution.
- Investment interest is strongest where India has cost advantages or import substitution potential.

## Investment Highlights
- Watch firms expanding manufacturing, exports, research, or distribution.
- Focus on segments with durable demand, pricing power, and policy support.

## Challenges & Risks
- Headline-only analysis can miss company-specific or customs-level detail.
- Input cost volatility, regulation, and execution risk can change the trade thesis quickly.
- Gemini fallback reason: {reason}

## Recommendations
- Validate this view with export-import statistics, company filings, and policy data.
- Compare the strongest subsegments before making a trade or investment decision.
- Treat the sources below as a starting point for deeper research.

## Sources
{source_lines}
"""


@app.get("/", tags=["Info"])
def root() -> Dict[str, str]:
    return {"message": "Trade Opportunities API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health", tags=["Info"])
def health() -> Dict[str, str]:
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
def analyze(sector: str, request: Request, api_key: str = Depends(verify_key)) -> AnalysisResponse:
    sector = sector.strip().lower()
    if len(sector) < 2 or len(sector) > 50:
        raise HTTPException(status_code=400, detail="Sector must be 2-50 characters.")
    if not sector.replace("-", "").replace(" ", "").isalpha():
        raise HTTPException(
            status_code=400,
            detail="Sector may only contain letters, spaces, or hyphens.",
        )

    remaining = check_rate(api_key)
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "api_key": api_key,
        "sector": sector,
        "started_at": utc_now_iso(),
        "status": "processing",
        "path": str(request.url.path),
    }
    logger.info("[%s] Analyzing sector '%s'", session_id, sector)

    try:
        news_items = search_news(sector)
        sessions[session_id]["news_items"] = len(news_items)
        logger.info("[%s] Collected %s news items", session_id, len(news_items))

        report_source = "gemini"
        try:
            report = call_gemini(sector, news_items)
        except HTTPException as exc:
            report_source = "fallback"
            logger.warning("[%s] Gemini failed, using fallback report: %s", session_id, exc.detail)
            report = build_fallback_report(sector, news_items, str(exc.detail))

        sessions[session_id]["status"] = "completed"
        sessions[session_id]["completed_at"] = utc_now_iso()
        sessions[session_id]["report_source"] = report_source

        return AnalysisResponse(
            session_id=session_id,
            sector=sector,
            generated_at=utc_now_iso(),
            requests_remaining=remaining,
            report=report,
        )
    except HTTPException:
        sessions[session_id]["status"] = "failed"
        raise
    except Exception as exc:
        sessions[session_id]["status"] = "failed"
        logger.exception("[%s] Unexpected error", session_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/sessions", tags=["Sessions"], summary="List your sessions")
def list_sessions(api_key: str = Depends(verify_key)) -> Dict[str, Any]:
    mine = {}
    for session_id, data in sessions.items():
        if data.get("api_key") != api_key:
            continue
        mine[session_id] = {key: value for key, value in data.items() if key != "api_key"}
    return {"count": len(mine), "sessions": mine}


@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Unexpected error."})
