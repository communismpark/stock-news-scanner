"""
alphavantage_fetcher.py — Fetch market news + sentiment via Alpha Vantage.
Includes per-article relevance and sentiment scores for pre-ranking.
"""
from datetime import datetime
import requests
import pytz
from config import ALPHA_VANTAGE_KEY, get_window


def fetch(window_start: datetime, window_end: datetime, tickers: list[str] = None) -> list[dict]:
    """
    Fetch news from Alpha Vantage News Sentiment API.
    If tickers provided, fetches ticker-specific news; otherwise fetches general market news.
    """
    if not ALPHA_VANTAGE_KEY:
        return []

    base_url = "https://www.alphavantage.co/query"
    time_from = window_start.strftime("%Y%m%dT%H%M")
    time_to = window_end.strftime("%Y%m%dT%H%M")

    params = {
        "function": "NEWS_SENTIMENT",
        "apikey": ALPHA_VANTAGE_KEY,
        "limit": 200,
        "time_from": time_from,
        "time_to": time_to,
        "sort": "LATEST",
    }

    if tickers:
        params["tickers"] = ",".join(tickers)
    else:
        params["topics"] = "financial_markets,economy_macro,earnings,ipo,mergers_and_acquisitions"

    try:
        resp = requests.get(base_url, params=params, timeout=15)
        data = resp.json()
    except Exception:
        return []

    articles = []
    for item in data.get("feed", []):
        pub_str = item.get("time_published", "")
        try:
            # Format: 20240315T093000
            pub_dt = datetime.strptime(pub_str, "%Y%m%dT%H%M%S").replace(tzinfo=pytz.utc)
        except Exception:
            continue

        if not (window_start <= pub_dt <= window_end):
            continue

        # Extract overall sentiment score and relevance for provided tickers
        relevance_score = 0.0
        sentiment_score = 0.0
        associated_tickers = []

        for ts in item.get("ticker_sentiment", []):
            t = ts.get("ticker", "")
            rel = float(ts.get("relevance_score", 0))
            snt = float(ts.get("ticker_sentiment_score", 0))
            if rel > 0.1:
                associated_tickers.append(t)
                relevance_score = max(relevance_score, rel)
                sentiment_score = snt

        # Overall sentiment label from the article
        overall_sentiment = item.get("overall_sentiment_label", "Neutral")

        section_hint = "major"
        if tickers:
            section_hint = "ticker"

        articles.append({
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "url": item.get("url", ""),
            "source": item.get("source", "Alpha Vantage"),
            "published_at": pub_dt,
            "tickers": associated_tickers,
            "section_hint": section_hint,
            # Alpha Vantage extras (used for pre-ranking before Claude)
            "av_relevance": relevance_score,
            "av_sentiment_score": sentiment_score,
            "av_sentiment_label": overall_sentiment,
        })

    return articles
