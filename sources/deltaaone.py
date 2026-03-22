"""
deltaaone.py — Scrape @DeItaone tweets via Nitter public instances.
Falls back gracefully if all instances are unavailable.
"""
from datetime import datetime
import pytz

try:
    from ntscraper import Nitter
    NTSCRAPER_AVAILABLE = True
except ImportError:
    NTSCRAPER_AVAILABLE = False

# Public Nitter instances to try in order
NITTER_INSTANCES = [
    "nitter.privacydev.net",
    "nitter.poast.org",
    "nitter.1d4.us",
    "nitter.kavin.rocks",
]

DELTAAONE_HANDLE = "DeItaone"

# @DeItaone posts very frequently (can be every minute during breaking news).
# Pre-market window is ~17h → up to ~1000 tweets. Fetch generously, then cap
# what we pass to Claude so the prompt stays manageable.
_FETCH_LIMIT = 1200      # max tweets to pull from Nitter
_CLAUDE_CAP  = 60        # most-recent tweets forwarded to the AI pipeline


def fetch(window_start: datetime, window_end: datetime) -> list[dict]:
    """
    Scrape @DeItaone tweets from Nitter.
    Returns up to _CLAUDE_CAP most-recent tweets in the window,
    or an empty list if Nitter is unavailable.
    """
    if not NTSCRAPER_AVAILABLE:
        return []

    results = None
    for instance in NITTER_INSTANCES:
        try:
            scraper = Nitter(log_level=1, skip_instance_check=False)
            results = scraper.get_tweets(
                DELTAAONE_HANDLE,
                mode="user",
                number=_FETCH_LIMIT,
                instance=instance,
            )
            if results and results.get("tweets"):
                break
        except Exception:
            results = None
            continue

    if not results or not results.get("tweets"):
        return []

    tweets = []
    for tweet in results.get("tweets", []):
        date_str = tweet.get("date", "")
        pub_dt = _parse_nitter_date(date_str)
        if pub_dt is None:
            continue

        # Nitter returns newest-first. Once we go past window_start we're done.
        if pub_dt < window_start:
            break

        if pub_dt > window_end:
            continue

        text = tweet.get("text", "").strip()
        if not text:
            continue

        link = tweet.get("link", "")
        tweets.append({
            "title": text[:120] + ("..." if len(text) > 120 else ""),
            "summary": text,
            "url": f"https://x.com/{DELTAAONE_HANDLE}/status/{_extract_id(link)}" if link else "",
            "source": "@DeItaone",
            "published_at": pub_dt,
            "tickers": _extract_tickers(text),
            "section_hint": "other",
        })

    # Already newest-first from Nitter; keep only the most recent _CLAUDE_CAP.
    return tweets[:_CLAUDE_CAP]


def _parse_nitter_date(date_str: str) -> datetime | None:
    """Parse Nitter date strings into UTC-aware datetimes."""
    if not date_str:
        return None
    # Formats ntscraper may return: "Mar 21, 2024 · 8:45 AM UTC"
    # or ISO-like strings
    clean = date_str.replace(" · ", " ").replace(" UTC", "").strip()
    for fmt in (
        "%b %d, %Y %I:%M %p",
        "%b %d, %Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(clean, fmt)
            return dt.replace(tzinfo=pytz.utc)
        except ValueError:
            continue
    return None


def _extract_id(link: str) -> str:
    """Extract tweet ID from a Nitter link."""
    parts = link.rstrip("/").split("/")
    return parts[-1] if parts else ""


def _extract_tickers(text: str) -> list[str]:
    """Extract $TICKER mentions from tweet text."""
    import re
    return re.findall(r"\$([A-Z]{1,5})", text)
