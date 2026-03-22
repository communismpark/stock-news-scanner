"""
yfinance_fetcher.py — Fetch per-ticker news and upgrades/downgrades via yfinance.
"""
from datetime import datetime
import yfinance as yf
import pytz


def fetch_ticker_news(ticker: str, window_start: datetime, window_end: datetime) -> list[dict]:
    """Fetch recent news for a single ticker."""
    articles = []
    try:
        t = yf.Ticker(ticker)
        news_items = t.news or []
    except Exception:
        return []

    for item in news_items:
        ts = item.get("providerPublishTime") or item.get("publishedAt")
        if ts is None:
            continue
        try:
            pub_dt = datetime.fromtimestamp(ts, tz=pytz.utc)
        except Exception:
            continue

        if not (window_start <= pub_dt <= window_end):
            continue

        articles.append({
            "title": item.get("title", ""),
            "summary": "",
            "url": item.get("link", ""),
            "source": item.get("publisher", "Yahoo Finance"),
            "published_at": pub_dt,
            "tickers": [ticker],
            "section_hint": "ticker",
        })

    return articles


def fetch_upgrades_downgrades(ticker: str, window_start: datetime) -> list[dict]:
    """
    Fetch analyst upgrades/downgrades for a ticker since window_start.
    Returns list of dicts: {ticker, firm, from_grade, to_grade, action, date}
    """
    results = []
    try:
        t = yf.Ticker(ticker)
        df = t.get_upgrades_downgrades()
        if df is None or df.empty:
            return []
    except Exception:
        return []

    # Index is GradeDate (datetime)
    try:
        df = df.reset_index()
        for _, row in df.iterrows():
            grade_date = row.get("GradeDate")
            if grade_date is None:
                continue
            if hasattr(grade_date, "tzinfo") and grade_date.tzinfo is None:
                grade_date = grade_date.replace(tzinfo=pytz.utc)
            elif not hasattr(grade_date, "tzinfo"):
                continue

            if grade_date < window_start:
                continue

            results.append({
                "ticker": ticker,
                "firm": row.get("Firm", ""),
                "from_grade": row.get("FromGrade", ""),
                "to_grade": row.get("ToGrade", ""),
                "action": row.get("Action", ""),
                "date": grade_date,
            })
    except Exception:
        pass

    return results


def fetch_all_for_tickers(
    tickers: list[str],
    window_start: datetime,
    window_end: datetime,
) -> tuple[list[dict], list[dict]]:
    """
    Fetch news + upgrades/downgrades for a list of tickers.
    Returns (news_articles, upgrades_downgrades).
    """
    all_news = []
    all_upgrades = []
    for ticker in tickers:
        all_news.extend(fetch_ticker_news(ticker, window_start, window_end))
        all_upgrades.extend(fetch_upgrades_downgrades(ticker, window_start))
    return all_news, all_upgrades
