"""
finnhub_fetcher.py — Fetch company news and analyst recommendations via Finnhub.
"""
from datetime import datetime
import finnhub
import pytz
from config import FINNHUB_KEY


def _get_client():
    if not FINNHUB_KEY:
        return None
    return finnhub.Client(api_key=FINNHUB_KEY)


def fetch_company_news(ticker: str, window_start: datetime, window_end: datetime) -> list[dict]:
    """Fetch company-specific news for a ticker."""
    client = _get_client()
    if not client:
        return []

    try:
        raw = client.company_news(
            ticker,
            _from=window_start.strftime("%Y-%m-%d"),
            to=window_end.strftime("%Y-%m-%d"),
        )
    except Exception:
        return []

    articles = []
    seen = set()
    for item in raw:
        url = item.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)

        ts = item.get("datetime")
        if ts is None:
            continue
        try:
            pub_dt = datetime.fromtimestamp(ts, tz=pytz.utc)
        except Exception:
            continue

        if not (window_start <= pub_dt <= window_end):
            continue

        articles.append({
            "title": item.get("headline", ""),
            "summary": item.get("summary", ""),
            "url": url,
            "source": item.get("source", "Finnhub"),
            "published_at": pub_dt,
            "tickers": [ticker],
            "section_hint": "ticker",
        })

    return articles


def fetch_market_news(window_start: datetime, window_end: datetime) -> list[dict]:
    """Fetch general market/forex/macro news."""
    client = _get_client()
    if not client:
        return []

    articles = []
    seen = set()
    for category in ("general", "forex", "merger"):
        try:
            raw = client.general_news(category, min_id=0)
        except Exception:
            continue

        for item in raw:
            url = item.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)

            ts = item.get("datetime")
            if not ts:
                continue
            try:
                pub_dt = datetime.fromtimestamp(ts, tz=pytz.utc)
            except Exception:
                continue

            if not (window_start <= pub_dt <= window_end):
                continue

            articles.append({
                "title": item.get("headline", ""),
                "summary": item.get("summary", ""),
                "url": url,
                "source": item.get("source", "Finnhub"),
                "published_at": pub_dt,
                "tickers": [],
                "section_hint": "major",
            })

    return articles


def fetch_all_for_tickers(
    tickers: list[str],
    window_start: datetime,
    window_end: datetime,
) -> list[dict]:
    all_news = []
    for ticker in tickers:
        all_news.extend(fetch_company_news(ticker, window_start, window_end))
    return all_news
