"""
newsapi_fetcher.py — Fetch general market/business headlines via NewsAPI.
Returns a list of article dicts in the common Article format.
"""
from datetime import datetime
from newsapi import NewsApiClient
import pytz
from config import NEWSAPI_KEY, get_window

# Common article schema used across all fetchers:
# {
#   "title": str,
#   "summary": str,        # description or snippet
#   "url": str,
#   "source": str,         # outlet name
#   "published_at": datetime (UTC-aware),
#   "tickers": list[str],  # associated tickers if known
#   "section_hint": str,   # "major" | "mag7" | "watchlist" | "other"
# }


def fetch(window_start: datetime, window_end: datetime) -> list[dict]:
    if not NEWSAPI_KEY:
        return []

    client = NewsApiClient(api_key=NEWSAPI_KEY)
    articles = []

    try:
        resp = client.get_top_headlines(
            category="business",
            language="en",
            page_size=100,
        )
        raw = resp.get("articles", [])
    except Exception:
        raw = []

    # Also search for financial/stock market news
    try:
        resp2 = client.get_everything(
            q="stock market OR earnings OR Federal Reserve OR S&P 500 OR Nasdaq",
            language="en",
            sort_by="publishedAt",
            page_size=100,
            from_param=window_start.strftime("%Y-%m-%dT%H:%M:%S"),
            to=window_end.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        raw += resp2.get("articles", [])
    except Exception:
        pass

    seen_urls = set()
    for a in raw:
        url = a.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        pub = a.get("publishedAt", "")
        try:
            pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except Exception:
            continue

        if not (window_start <= pub_dt <= window_end):
            continue

        articles.append({
            "title": a.get("title") or "",
            "summary": a.get("description") or "",
            "url": url,
            "source": a.get("source", {}).get("name", "NewsAPI"),
            "published_at": pub_dt,
            "tickers": [],
            "section_hint": "major",
        })

    return articles
