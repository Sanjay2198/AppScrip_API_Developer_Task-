import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List
import httpx
from utils import clean_text

logger = logging.getLogger(__name__)


def _build_queries(sector: str) -> List[str]:
    current_year = datetime.now(timezone.utc).year
    return [
        f"{sector} India trade {current_year}",
        f"{sector} India export import market",
        f"{sector} India investment opportunities",
    ]


async def _fetch_query(client: httpx.AsyncClient, query: str) -> List[str]:
    url = (
        "https://news.google.com/rss/search"
        f"?q={query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
    )
    response = await client.get(url)
    response.raise_for_status()

    root = ET.fromstring(response.text)
    items: List[str] = []
    for item in root.findall(".//item")[:4]:
        title = clean_text(item.findtext("title", ""))
        description = clean_text(item.findtext("description", ""))
        line = title if not description else f"{title} - {description}"
        if line:
            items.append(line)
    return items


async def collect_market_news(sector: str) -> List[str]:
    queries = _build_queries(sector)
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        results = await asyncio.gather(
            *[_fetch_query(client, query) for query in queries],
            return_exceptions=True,
        )

    items: List[str] = []
    seen = set()
    for query, result in zip(queries, results):
        if isinstance(result, Exception):
            logger.warning("News search failed for '%s': %s", query, result)
            continue
        for line in result:
            normalized = line.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            items.append(line)

    return items[:9]
