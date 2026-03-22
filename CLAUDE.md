# Stock News Scanner — Claude Code Guide

Pre-market day trader news scanner. Covers yesterday 4:00 PM ET → today's market open.

## Run

```bash
py -3.13 scanner.py
```

Requires a `.env` file in the project root (see `.env.example`). Copy it and fill in keys:

```
NEWSAPI_KEY=...
FINNHUB_KEY=...
ALPHA_VANTAGE_KEY=...
ANTHROPIC_API_KEY=sk-...
ANTHROPIC_BASE_URL=https://www.elbnt.ai   # custom proxy; SDK reads this automatically
```

## Project Structure

```
scanner.py                  # entry point — orchestrates parallel fetch + render
config.py                   # API keys, MAG7 list, time window, RSS feed list
watchlist.txt               # one ticker per line; Section 3 tickers
requirements.txt

fetchers/
  newsapi_fetcher.py        # NewsAPI general headlines
  alphavantage_fetcher.py   # Alpha Vantage (relevance/sentiment scored)
  rss_fetcher.py            # feedparser — CNBC, MarketWatch, Investing.com, SA
  yfinance_fetcher.py       # per-ticker news + get_upgrades_downgrades()
  finnhub_fetcher.py        # per-ticker + general market/forex/merger news

sources/
  deltaaone.py              # @DeItaone tweets via ntscraper (Nitter); fetches up to 1200,
                            #   caps at 60 most-recent before Claude; graceful fallback

ai/
  editor.py                 # Claude editorial pipeline — dedup, filter, summarize → JSON

display/
  renderer.py               # Rich terminal — 4 colored sections
```

## Four Output Sections

| # | Color | Content |
|---|-------|---------|
| 1 | Red | Major news + 1-3 macro trading themes synthesized by Claude |
| 2 | Blue | Mag 7: AAPL MSFT GOOGL AMZN META NVDA TSLA |
| 3 | Green | Watchlist tickers (from `watchlist.txt`) |
| 4 | Dim | @DeItaone tweets + other remaining headlines |

Analyst upgrades/downgrades (via yfinance) appear as tables at the top of Sections 2 and 3.

## Data Flow

1. `scanner.py` fans out to all fetchers via `ThreadPoolExecutor(max_workers=12)`
2. All raw articles collected into 4 pools (major, mag7, watchlist, other)
3. `editor.run_editorial_pipeline()` — URL-hash dedup, then single Claude round-trip
4. Claude returns structured JSON: deduped, filtered, summarized
5. `renderer.render_all()` displays result with Rich

## AI Editorial Pipeline (`ai/editor.py`)

- **Stage 1**: URL-hash dedup (cheap, no API call)
- **Stage 2**: Single Claude prompt with all 4 pools + upgrade rows → structured JSON
- **Model**: `claude-haiku-4-5-20251001` (fast, cheap, sufficient)
- **Fallback**: if `ANTHROPIC_API_KEY` missing or Claude errors → raw headlines shown with warning banner
- Claude drops: opinion/recap/evergreen articles; keeps: earnings, Fed data, M&A, upgrades, pre-market movers

## Key Design Decisions

- Claude is an **editor** (dedup + filter + summarize), not just a summarizer
- Alpha Vantage provides relevance/sentiment scores used for pre-ranking before Claude sees articles
- Watchlist tickers with no news are **suppressed** from output (Section 3 only shows active tickers)
- **`@DeItaone` volume handling**: fetches up to 1,200 tweets (`_FETCH_LIMIT`), early-breaks once past `window_start` (Nitter is newest-first), then caps at 60 (`_CLAUDE_CAP`) before passing to Claude — tune these constants in `sources/deltaaone.py`
- `_safe()` in renderer strips non-ASCII chars as a safety net

## Scheduled Execution (Windows Task Scheduler)

```
Program:   py
Arguments: -3.13 "D:\py projects\stock-news-scanner\scanner.py"
Start in:  D:\py projects\stock-news-scanner
Trigger:   Daily at 9:15 AM
```

## Adding Watchlist Tickers

Edit `watchlist.txt` — one ticker per line, `#` for comments:

```
AMD
INTC
BA
# JPM  ← commented out
```

## Python Version

**Python 3.13** (`py -3.13`). Do not use the system Python 3.8.

## Git / GitHub

Remote: `https://github.com/communismpark/stock-news-scanner`

`.env` is gitignored. Never commit API keys. Use `.env.example` as the template.
