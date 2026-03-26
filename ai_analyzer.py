from typing import Any, Dict, List

import httpx

from config import settings
from utils import clean_text

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


class AnalysisServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def build_prompt(sector: str, news_items: List[str]) -> str:
    news_block = "\n".join(f"- {item}" for item in news_items)
    if not news_block:
        news_block = "- No live Google News items were available. Use general sector knowledge and state assumptions clearly."
    return PROMPT_TEMPLATE.format(sector=sector.title(), news_block=news_block)


def extract_gemini_text(payload: Dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise AnalysisServiceError("Gemini returned no candidates.")

    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text = "\n".join(part.get("text", "") for part in parts if part.get("text")).strip()
    if not text:
        raise AnalysisServiceError("Gemini response did not contain report text.")
    return text


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


async def generate_market_report(sector: str, news_items: List[str]) -> str:
    if not settings.gemini_api_key:
        raise AnalysisServiceError("GEMINI_API_KEY is not configured.", status_code=503)

    payload = {
        "contents": [{"parts": [{"text": build_prompt(sector, news_items)}]}],
        "generationConfig": {"temperature": 0.3},
    }

    candidate_models = []
    for model_name in [settings.gemini_model, "gemini-2.5-flash", "gemini-2.0-flash"]:
        if model_name and model_name not in candidate_models:
            candidate_models.append(model_name)

    last_error = "Gemini request failed."
    async with httpx.AsyncClient(timeout=60) as client:
        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"x-goog-api-key": settings.gemini_api_key},
                )
            except httpx.ConnectError as exc:
                raise AnalysisServiceError("Cannot reach Gemini. Check your network.", status_code=503) from exc
            except httpx.TimeoutException as exc:
                raise AnalysisServiceError("Gemini request timed out.", status_code=504) from exc

            if response.status_code == 404:
                last_error = f"Model '{model_name}' was not found."
                continue
            if response.status_code == 429:
                raise AnalysisServiceError("Gemini rate limit hit. Try again later.", status_code=429)
            if response.status_code in {401, 403}:
                raise AnalysisServiceError("Gemini API key is invalid or unauthorized.", status_code=500)
            if not response.is_success:
                detail = clean_text(response.text)[:200] or "Unknown Gemini error."
                raise AnalysisServiceError(f"Gemini request failed: {detail}", status_code=502)

            return extract_gemini_text(response.json())

    raise AnalysisServiceError(last_error, status_code=502)
