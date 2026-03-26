import logging
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


def collect_market_data(sector: str) -> str:
    """
    Search DuckDuckGo for recent market news about the given sector in India.
    Returns collected text snippets as a single string.
    """
    queries = [
        f"{sector} sector India trade opportunities 2025",
        f"{sector} India market trends exports imports",
        f"{sector} India investment news current",
    ]

    collected = []

    for query in queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                url = r.get("href", "")
                if title or body:
                    collected.append(f"**{title}**\n{body}\nSource: {url}")
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed for '{query}': {e}")

    if not collected:
        logger.warning(f"No search results found for sector: {sector}")
        return f"No live search results available for '{sector}'. Provide a general analysis based on known data."

    return "\n\n---\n\n".join(collected[:9])  # max 9 snippets
