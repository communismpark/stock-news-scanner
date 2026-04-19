"""
config.py — Central configuration for the stock news scanner.
"""
import os
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

load_dotenv(override=True)

# ── API Keys ────────────────────────────────────────────────────────────────
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
FINNHUB_KEY = os.getenv("FINNHUB_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Email ────────────────────────────────────────────────────────────────────
EMAIL_FROM      = os.getenv("EMAIL_FROM", "")
EMAIL_TO        = os.getenv("EMAIL_TO", "")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD", "")
EMAIL_SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))

def check_keys():
    """Warn (don't crash) if any API key is missing."""
    missing = []
    for name, val in [
        ("NEWSAPI_KEY", NEWSAPI_KEY),
        ("FINNHUB_KEY", FINNHUB_KEY),
        ("ALPHA_VANTAGE_KEY", ALPHA_VANTAGE_KEY),
        ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
    ]:
        if not val:
            missing.append(name)
    return missing

# ── Tickers ──────────────────────────────────────────────────────────────────
MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]

def load_watchlist(path: str = "watchlist.txt") -> list[str]:
    """Load tickers from watchlist.txt, stripping comments and blanks."""
    tickers = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    tickers.append(line.upper())
    except FileNotFoundError:
        pass
    return tickers

# ── Time Window ───────────────────────────────────────────────────────────────
ET = pytz.timezone("America/New_York")

def get_window() -> tuple[datetime, datetime]:
    """
    Returns (start, end) in UTC.
    Start = yesterday 4:00 PM ET (previous market close).
    End   = now.
    """
    now_et = datetime.now(ET) - timedelta(days=3)
    # If it's before 4 PM today, yesterday's close = yesterday at 4 PM
    # If it's after 4 PM today (post-market), yesterday's close = today at 4 PM
    today_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    if now_et < today_close:
        start_et = today_close - timedelta(days=1)
    else:
        start_et = today_close
    return start_et.astimezone(pytz.utc), datetime.now(pytz.utc)

# ── RSS Feed URLs ─────────────────────────────────────────────────────────────
RSS_FEEDS = [
    ("CNBC Markets",     "https://www.cnbc.com/id/20409666/device/rss/rss.html"),
    ("CNBC Earnings",    "https://www.cnbc.com/id/15839135/device/rss/rss.html"),
    ("MarketWatch Top",  "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("MarketWatch MktP", "https://feeds.content.dowjones.io/public/rss/mw_marketpulse"),
    ("Investing.com",    "https://www.investing.com/rss/news.rss"),
    ("Seeking Alpha",    "https://seekingalpha.com/feed.xml"),
]

# ── Claude Model ──────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-6"
