import logging
from typing import List
import httpx
from config import settings

logger = logging.getLogger(__name__)

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

FREE_MODELS = [
    "meta-llama/llama-3.1-8b-instruct:free",
    "meta-llama/llama-3-8b-instruct:free",
    "google/gemma-2-9b-it:free",
    "microsoft/phi-3-mini-128k-instruct:free",
    "qwen/qwen-2-7b-instruct:free",
]


class AnalysisServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def build_prompt(sector: str, news_items: List[str]) -> str:
    news_block = "\n".join(f"- {item}" for item in news_items)
    if not news_block:
        news_block = "- No live news available. Use general sector knowledge and state assumptions clearly."
    return PROMPT_TEMPLATE.format(sector=sector.title(), news_block=news_block)


def build_fallback_report(sector: str, news_items: List[str], reason: str) -> str:
    sources = "\n".join(f"- {item}" for item in news_items) or "- No live news available."
    return f"""# Trade Opportunities Report: {sector.title()} Sector in India

## Executive Summary
This report is based on recent news headlines for the {sector} sector in India.
AI analysis was unavailable ({reason}), so this is a structured summary of collected news.

## Current Market Overview
Recent headlines indicate ongoing activity in the {sector} sector in India covering
trade volumes, regulatory changes, investment flows, and market dynamics.

## Trade Opportunities
### Export Opportunities
- Monitor export-oriented companies in the {sector} space for growth signals.
- Track government policy announcements supporting exports in this sector.

### Import Opportunities
- Identify critical raw materials or technology imports that strengthen domestic capacity.

## Key Trends
- Policy and regulatory updates are shaping near-term market direction.
- Supply chain resilience and capacity expansion remain priorities.
- Investment interest is growing in high-margin subsegments.

## Investment Highlights
- Watch for capacity expansion announcements and new partnerships.
- Focus on firms with durable demand and pricing power.

## Challenges & Risks
- Input cost volatility and global demand fluctuations pose risks.
- Regulatory changes can quickly affect market access.

## Recommendations
- Validate findings with official export-import data and company filings.
- Focus on the strongest subsegments before making trade decisions.

## Sources
{sources}
"""


async def generate_market_report(sector: str, news_items: List[str]) -> str:
    if not settings.openrouter_api_key:
        raise AnalysisServiceError("OPENROUTER_API_KEY is not configured.", status_code=503)

    prompt = build_prompt(sector, news_items)
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}

    async with httpx.AsyncClient(timeout=60) as client:
        for model in FREE_MODELS:
            try:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={"model": model, "messages": [{"role": "user", "content": prompt}]},
                )
                if response.status_code == 404:
                    logger.warning("Model %s not found, trying next...", model)
                    continue
                if response.status_code == 429:
                    raise AnalysisServiceError("Rate limit hit. Try again in a minute.", status_code=429)
                if not response.is_success:
                    logger.warning("Model %s failed: %s", model, response.text[:100])
                    continue
                logger.info("Success with model: %s", model)
                return response.json()["choices"][0]["message"]["content"]
            except AnalysisServiceError:
                raise
            except httpx.ConnectError:
                raise AnalysisServiceError("Cannot reach OpenRouter. Check your network.", status_code=503)

    raise AnalysisServiceError("All AI models failed.", status_code=502)
