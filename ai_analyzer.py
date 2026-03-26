import logging
import google.generativeai as genai
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

PROMPT_TEMPLATE = """
You are a trade and market analyst specializing in Indian industry sectors.

Based on the market data below, write a structured trade opportunities report for the **{sector}** sector in India.

--- MARKET DATA ---
{market_data}
--- END DATA ---

Generate the report in Markdown format using this exact structure:

# Trade Opportunities Report: {sector_title} Sector in India

## Executive Summary
(2-3 sentence overview of the sector's current state)

## Current Market Overview
(Market size, key players, current conditions)

## Trade Opportunities
### Export Opportunities
(List the top export opportunities with brief details)

### Import Opportunities
(List the key import areas)

## Key Trends
(3-5 important trends shaping this sector)

## Investment Highlights
(Notable investment opportunities and incentives)

## Challenges & Risks
(Main challenges traders and investors should be aware of)

## Recommendations
(3-5 concrete, actionable recommendations for traders/investors)

## Sources
(Mention the data sources referenced)

Keep the report factual, concise, and actionable. Focus on 2024-2025 context.
"""


def analyze_with_gemini(sector: str, market_data: str) -> str:
    """Send collected data to Gemini and return a markdown analysis report."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in environment variables.")

    prompt = PROMPT_TEMPLATE.format(
        sector=sector,
        sector_title=sector.title(),
        market_data=market_data
    )

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise RuntimeError(f"AI analysis failed: {str(e)}")
