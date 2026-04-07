import asyncio
import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
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
    "nvidia/nemotron-3-super-120b-a12b:free",
    "stepfun/step-3.5-flash:free",
    "arcee-ai/trinity-large-preview:free",
    "liquid/lfm-2.5-1.2b-instruct:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
]


class AnalysisServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _clean(value: str) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


async def _fetch_query(client: httpx.AsyncClient, query: str) -> List[str]:
    url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
    response = await client.get(url)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    items: List[str] = []
    for item in root.findall(".//item")[:4]:
        title = _clean(item.findtext("title", ""))
        desc = _clean(item.findtext("description", ""))
        line = title if not desc else f"{title} - {desc}"
        if line:
            items.append(line)
    return items


async def collect_market_news(sector: str) -> List[str]:
    year = datetime.now(timezone.utc).year
    queries = [
        f"{sector} India trade {year}",
        f"{sector} India export import market",
        f"{sector} India investment opportunities",
    ]
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        results = await asyncio.gather(*[_fetch_query(client, q) for q in queries], return_exceptions=True)

    items: List[str] = []
    seen: set = set()
    for query, result in zip(queries, results):
        if isinstance(result, Exception):
            logger.warning("News search failed for '%s': %s", query, result)
            continue
        for line in result:
            if line.lower() not in seen:
                seen.add(line.lower())
                items.append(line)
    return items[:9]


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


async def _try_gemini(prompt: str, client: httpx.AsyncClient) -> str:
    if not settings.gemini_api_key:
        raise AnalysisServiceError("No Gemini key.", status_code=503)
    for model in ["gemini-2.0-flash", "gemini-2.0-flash-lite"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            response = await client.post(
                url,
                headers={"x-goog-api-key": settings.gemini_api_key},
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise AnalysisServiceError(f"Gemini connection error: {e}", status_code=502)
        if response.status_code == 404:
            continue
        if response.status_code == 429:
            raise AnalysisServiceError("Gemini rate limit. Try again later.", status_code=429)
        if not response.is_success:
            raise AnalysisServiceError(f"Gemini error {response.status_code}", status_code=502)
        candidates = response.json().get("candidates", [])
        text = candidates[0]["content"]["parts"][0]["text"].strip() if candidates else ""
        if text:
            logger.info("Success with Gemini model: %s", model)
            return text
    raise AnalysisServiceError("Gemini models not available.", status_code=502)


async def _try_openrouter(prompt: str, client: httpx.AsyncClient) -> str:
    if not settings.openrouter_api_key:
        raise AnalysisServiceError("No OpenRouter key.", status_code=503)
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
    for model in FREE_MODELS:
        try:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning("OpenRouter connection error for %s: %s", model, e)
            continue
        if response.status_code == 404:
            logger.warning("OpenRouter model %s not found, trying next...", model)
            continue
        if response.status_code == 429:
            raise AnalysisServiceError("OpenRouter rate limit. Try again later.", status_code=429)
        if not response.is_success:
            logger.warning("OpenRouter model %s failed: %s", model, response.text[:80])
            continue
        logger.info("Success with OpenRouter model: %s", model)
        return response.json()["choices"][0]["message"]["content"]
    raise AnalysisServiceError("All OpenRouter models failed.", status_code=502)


async def generate_market_report(sector: str, news_items: List[str]) -> str:
    news_block = "\n".join(f"- {item}" for item in news_items) or "- No live news available. Use general sector knowledge."
    prompt = PROMPT_TEMPLATE.format(sector=sector.title(), news_block=news_block)
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            return await _try_gemini(prompt, client)
        except AnalysisServiceError as e:
            logger.warning("Gemini failed (%s), trying OpenRouter...", e.message)
        try:
            return await _try_openrouter(prompt, client)
        except AnalysisServiceError:
            raise
    raise AnalysisServiceError("All AI providers failed.", status_code=502)
