"""
rss_fetcher.py — Fetch news from RSS feeds (CNBC, MarketWatch, Investing.com, etc.)
No API key required.
"""
from datetime import datetime
from email.utils import parsedate_to_datetime
import feedparser
import pytz
from config import RSS_FEEDS


def _parse_date(entry) -> datetime | None:
    """Try to extract a timezone-aware UTC datetime from a feed entry."""
    # feedparser normalises to 9-tuple in published_parsed
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
            return dt
        except Exception:
            pass
    # Fallback: raw string
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            return dt.astimezone(pytz.utc)
        except Exception:
            pass
    return None


def fetch(window_start: datetime, window_end: datetime) -> list[dict]:
    articles = []
    seen_urls = set()

    for feed_name, feed_url in RSS_FEEDS:
        try:
            d = feedparser.parse(feed_url)
        except Exception:
            continue

        for entry in d.entries:
            url = getattr(entry, "link", "") or ""
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            pub_dt = _parse_date(entry)
            if pub_dt is None:
                continue

            if not (window_start <= pub_dt <= window_end):
                continue

            title = getattr(entry, "title", "") or ""
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
            # Strip HTML tags from summary (simple approach)
            import re
            summary = re.sub(r"<[^>]+>", "", summary).strip()

            articles.append({
                "title": title,
                "summary": summary[:500],
                "url": url,
                "source": feed_name,
                "published_at": pub_dt,
                "tickers": [],
                "section_hint": "major",
            })

    return articles
