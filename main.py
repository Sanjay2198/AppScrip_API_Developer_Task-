import uuid
import logging
from datetime import datetime

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from auth import verify_api_key
from rate_limiter import check_rate_limit, get_remaining_requests
from data_collector import collect_market_data
from ai_analyzer import analyze_with_gemini

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Trade Opportunities API",
    description=(
        "Analyzes market data and generates structured trade opportunity reports "
        "for specific sectors in India. Powered by DuckDuckGo search + Google Gemini."
    ),
    version="1.0.0",
)

# In-memory session store  { session_id: {...} }
sessions: dict = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["Info"])
def root():
    """API info and links."""
    return {
        "message": "Trade Opportunities API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Info"])
def health_check():
    """Simple health check."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get(
    "/analyze/{sector}",
    tags=["Analysis"],
    summary="Get trade opportunities report for a sector",
    response_description="A structured markdown report with trade insights",
)
def analyze_sector(
    sector: str,
    request: Request,
    api_key: str = Depends(verify_api_key),
):
    """
    Accepts a **sector** name (e.g. *pharmaceuticals*, *technology*, *agriculture*)
    and returns a structured Markdown report with current trade opportunities in India.

    **Authentication:** Pass your API key in the `X-Api-Key` header.

    **Rate limit:** 10 requests per hour per API key.
    """
    # --- Input validation ---
    sector = sector.strip().lower()
    if len(sector) < 2 or len(sector) > 50:
        raise HTTPException(status_code=400, detail="Sector name must be 2–50 characters.")
    if not sector.replace("-", "").replace(" ", "").isalpha():
        raise HTTPException(
            status_code=400,
            detail="Sector name may only contain letters, spaces, or hyphens."
        )

    # --- Rate limiting ---
    check_rate_limit(api_key)

    # --- Session ---
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "sector": sector,
        "api_key": api_key,
        "client_ip": request.client.host if request.client else "unknown",
        "started_at": datetime.utcnow().isoformat(),
        "status": "processing",
    }
    logger.info(f"[{session_id}] Starting analysis for sector='{sector}'")

    try:
        # Step 1 – collect market data via web search
        logger.info(f"[{session_id}] Collecting market data …")
        market_data = collect_market_data(sector)

        # Step 2 – analyse with Gemini
        logger.info(f"[{session_id}] Running Gemini analysis …")
        report = analyze_with_gemini(sector, market_data)

        sessions[session_id]["status"] = "completed"
        sessions[session_id]["completed_at"] = datetime.utcnow().isoformat()
        logger.info(f"[{session_id}] Analysis complete.")

        return {
            "session_id": session_id,
            "sector": sector,
            "generated_at": datetime.utcnow().isoformat(),
            "requests_remaining": get_remaining_requests(api_key),
            "report": report,
        }

    except HTTPException:
        raise
    except Exception as e:
        sessions[session_id]["status"] = "failed"
        sessions[session_id]["error"] = str(e)
        logger.error(f"[{session_id}] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions", tags=["Sessions"], summary="List your sessions")
def list_sessions(api_key: str = Depends(verify_api_key)):
    """
    Returns all analysis sessions created with the current API key.
    Useful for tracking request history.
    """
    user_sessions = {
        sid: data
        for sid, data in sessions.items()
        if data.get("api_key") == api_key
    }
    return {"count": len(user_sessions), "sessions": user_sessions}


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
def global_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )
