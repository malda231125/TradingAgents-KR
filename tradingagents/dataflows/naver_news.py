"""Naver News Search API integration for TradingAgents Korea.

Uses the Naver Open API (non-login type) to search Korean news articles.
Requires NAVER_CLIENT_ID and NAVER_CLIENT_SECRET environment variables.

API reference: https://developers.naver.com/docs/serviceapi/search/news/news.md
Rate limit: 25,000 calls/day
"""

import logging
import os
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

NAVER_NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json"


def _get_naver_credentials():
    """Get Naver API credentials from environment."""
    client_id = os.environ.get("NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
    return client_id, client_secret


def _naver_available() -> bool:
    """Check if Naver API credentials are configured."""
    client_id, client_secret = _get_naver_credentials()
    return bool(client_id and client_secret)


def _search_naver_news(
    query: str,
    display: int = 10,
    start: int = 1,
    sort: str = "date",
) -> dict:
    """Call the Naver News Search API.

    Args:
        query: Search query string
        display: Number of results (1-100, default 10)
        start: Start position (1-1000, default 1)
        sort: Sort order - "date" (newest) or "sim" (relevance)

    Returns:
        API response dict with 'items' list

    Raises:
        RuntimeError: If API call fails or credentials missing
    """
    client_id, client_secret = _get_naver_credentials()
    if not client_id or not client_secret:
        raise RuntimeError(
            "Naver API credentials not configured. "
            "Set NAVER_CLIENT_ID and NAVER_CLIENT_SECRET environment variables."
        )

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {
        "query": query,
        "display": min(display, 100),
        "start": start,
        "sort": sort,
    }

    try:
        response = requests.get(
            NAVER_NEWS_API_URL, headers=headers, params=params, timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Naver News API request failed: {e}")


def _clean_html(text: str) -> str:
    """Remove HTML tags from Naver API response text."""
    import re
    clean = re.sub(r"<[^>]+>", "", text)
    clean = clean.replace("&quot;", '"').replace("&amp;", "&")
    clean = clean.replace("&lt;", "<").replace("&gt;", ">")
    clean = clean.replace("&apos;", "'")
    return clean.strip()


def _format_news_items(items: list) -> str:
    """Format Naver news items into a readable report."""
    if not items:
        return "No news articles found."

    lines = []
    for i, item in enumerate(items, 1):
        title = _clean_html(item.get("title", ""))
        description = _clean_html(item.get("description", ""))
        pub_date = item.get("pubDate", "")
        link = item.get("originallink", item.get("link", ""))

        lines.append(f"[{i}] {title}")
        lines.append(f"    Date: {pub_date}")
        lines.append(f"    Summary: {description}")
        lines.append(f"    Link: {link}")
        lines.append("")

    return "\n".join(lines)


def get_news_naver(
    ticker: str,
    start_date: str,
    end_date: str,
) -> str:
    """Get company-specific Korean news via Naver Search API.

    Args:
        ticker: Company name or ticker symbol (e.g. "삼성전자", "005930")
        start_date: Start date (yyyy-mm-dd) — used for context, Naver API sorts by date
        end_date: End date (yyyy-mm-dd)

    Returns:
        Formatted string of news articles
    """
    if not _naver_available():
        raise RuntimeError("Naver API credentials not configured")

    # Search with ticker as query — Naver handles Korean company names well
    query = f"{ticker} 주식"

    try:
        result = _search_naver_news(query=query, display=15, sort="date")
        items = result.get("items", [])

        if not items:
            return f"No Korean news found for '{ticker}' via Naver News API."

        header = f"=== Naver News Search Results for '{ticker}' ===\n"
        header += f"Query: {query} | Period: {start_date} to {end_date}\n"
        header += f"Total results available: {result.get('total', 'N/A')}\n"
        header += f"Showing: {len(items)} articles\n\n"

        return header + _format_news_items(items)

    except Exception as e:
        logger.warning("Naver news fetch failed for %s: %s", ticker, e)
        raise


def get_global_news_naver(
    curr_date: str,
    look_back_days: int = 7,
    limit: int = 10,
) -> str:
    """Get global/macro news relevant to Korean markets via Naver.

    Args:
        curr_date: Current date (yyyy-mm-dd)
        look_back_days: How many days to look back
        limit: Max articles to return

    Returns:
        Formatted string of global/macro news
    """
    if not _naver_available():
        raise RuntimeError("Naver API credentials not configured")

    # Korean market macro keywords
    queries = [
        "코스피 코스닥 증시",
        "한국 경제 금리 환율",
    ]

    all_items = []
    for query in queries:
        try:
            result = _search_naver_news(
                query=query, display=min(limit, 20), sort="date"
            )
            all_items.extend(result.get("items", []))
        except Exception as e:
            logger.warning("Naver global news query '%s' failed: %s", query, e)

    if not all_items:
        return "No Korean macro/global news found via Naver News API."

    # Deduplicate by title
    seen_titles = set()
    unique_items = []
    for item in all_items:
        title = _clean_html(item.get("title", ""))
        if title not in seen_titles:
            seen_titles.add(title)
            unique_items.append(item)

    unique_items = unique_items[:limit]

    dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_date = (dt - timedelta(days=look_back_days)).strftime("%Y-%m-%d")

    header = f"=== Naver Global/Macro News for Korean Markets ===\n"
    header += f"Period: {start_date} to {curr_date}\n"
    header += f"Showing: {len(unique_items)} articles\n\n"

    return header + _format_news_items(unique_items)
