"""
scanner.py — Pre-Market Stock News Scanner for Day Traders
=============================================================
Covers the window: yesterday 4:00 PM ET → now (today's market open)

USAGE:
  python scanner.py

SCHEDULED (Windows Task Scheduler):
  Action: Start a program
  Program: python
  Arguments: "D:\\py projects\\stock-news-scanner\\scanner.py"
  Start in: D:\\py projects\\stock-news-scanner
  Trigger: Daily at 8:30 AM

SECTIONS:
  1. Major News & Trading Thesis  (macro themes for the day)
  2. Mag 7                        (AAPL MSFT GOOGL AMZN META NVDA TSLA)
  3. Watchlist                    (your tickers in watchlist.txt)
  4. Other Notable News           (@DeItaone + remaining headlines)
"""

import concurrent.futures
import sys

from config import (
    MAG7,
    check_keys,
    get_window,
    load_watchlist,
)

from fetchers import (
    newsapi_fetcher,
    alphavantage_fetcher,
    rss_fetcher,
    yfinance_fetcher,
    finnhub_fetcher,
)
from sources import deltaaone
from ai import editor
from display import renderer


def main():
    # ── Startup checks ────────────────────────────────────────────────────────
    missing = check_keys()
    if missing:
        renderer.render_warning(
            f"Missing API keys (set in .env): {', '.join(missing)}\n"
            "  Affected sources will be skipped."
        )

    window_start, window_end = get_window()
    watchlist = load_watchlist()
    all_tickers_section3 = watchlist  # user's watchlist

    # ── Fetch all data in parallel ─────────────────────────────────────────────
    renderer.console.print("[dim]Fetching news...[/]", end=" ")

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        # Major/general news
        f_newsapi     = pool.submit(newsapi_fetcher.fetch, window_start, window_end)
        f_av_major    = pool.submit(alphavantage_fetcher.fetch, window_start, window_end)
        f_rss         = pool.submit(rss_fetcher.fetch, window_start, window_end)
        f_fh_market   = pool.submit(finnhub_fetcher.fetch_market_news, window_start, window_end)

        # Mag 7 ticker-specific news + upgrades
        f_yf_mag7     = pool.submit(yfinance_fetcher.fetch_all_for_tickers, MAG7, window_start, window_end)
        f_av_mag7     = pool.submit(alphavantage_fetcher.fetch, window_start, window_end, MAG7)
        f_fh_mag7     = pool.submit(finnhub_fetcher.fetch_all_for_tickers, MAG7, window_start, window_end)

        # Watchlist ticker-specific news + upgrades
        if all_tickers_section3:
            f_yf_wl   = pool.submit(yfinance_fetcher.fetch_all_for_tickers, all_tickers_section3, window_start, window_end)
            f_av_wl   = pool.submit(alphavantage_fetcher.fetch, window_start, window_end, all_tickers_section3)
            f_fh_wl   = pool.submit(finnhub_fetcher.fetch_all_for_tickers, all_tickers_section3, window_start, window_end)
        else:
            f_yf_wl = f_av_wl = f_fh_wl = None

        # @DeItaone
        f_deltaaone   = pool.submit(deltaaone.fetch, window_start, window_end)

    renderer.console.print("[green]done[/]")

    # ── Collect results ────────────────────────────────────────────────────────
    newsapi_articles  = _safe(f_newsapi, [])
    av_major_articles = _safe(f_av_major, [])
    rss_articles      = _safe(f_rss, [])
    fh_market_articles= _safe(f_fh_market, [])

    yf_mag7_news, upgrades_mag7 = _safe(f_yf_mag7, ([], []))
    av_mag7_articles  = _safe(f_av_mag7, [])
    fh_mag7_articles  = _safe(f_fh_mag7, [])

    if f_yf_wl:
        yf_wl_news, upgrades_watchlist = _safe(f_yf_wl, ([], []))
        av_wl_articles  = _safe(f_av_wl, [])
        fh_wl_articles  = _safe(f_fh_wl, [])
    else:
        yf_wl_news = []
        upgrades_watchlist = []
        av_wl_articles = []
        fh_wl_articles = []

    deltaaone_tweets  = _safe(f_deltaaone, [])
    deltaaone_ok      = len(deltaaone_tweets) > 0

    # ── Aggregate into section pools ──────────────────────────────────────────
    # Section 1: all general/macro news
    major_pool = newsapi_articles + av_major_articles + rss_articles + fh_market_articles

    # Section 2: Mag 7 news
    mag7_pool = yf_mag7_news + av_mag7_articles + fh_mag7_articles

    # Section 3: Watchlist news
    watchlist_pool = yf_wl_news + av_wl_articles + fh_wl_articles

    # Section 4: @DeItaone + overflow
    other_pool = deltaaone_tweets

    renderer.console.print(
        f"[dim]Raw articles: {len(major_pool)} major | {len(mag7_pool)} mag7 | "
        f"{len(watchlist_pool)} watchlist | {len(other_pool)} other[/]"
    )
    renderer.console.print("[dim]Running editorial pass (Claude)...[/]", end=" ")

    # ── Claude editorial pipeline ──────────────────────────────────────────────
    result = editor.run_editorial_pipeline(
        major_articles=major_pool,
        mag7_articles=mag7_pool,
        watchlist_articles=watchlist_pool,
        other_articles=other_pool,
        mag7_tickers=MAG7,
        watchlist_tickers=all_tickers_section3,
        upgrades_mag7=upgrades_mag7,
        upgrades_watchlist=upgrades_watchlist,
        deltaaone_available=deltaaone_ok,
    )

    renderer.console.print("[green]done[/]")

    # ── Render ────────────────────────────────────────────────────────────────
    renderer.render_all(result, window_start, window_end)


def _safe(future, default):
    """Return future result or default on exception."""
    if future is None:
        return default
    try:
        return future.result()
    except Exception as e:
        return default


if __name__ == "__main__":
    main()
