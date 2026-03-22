"""
editor.py — Claude editorial pipeline.

Three stages:
  1. URL-based deduplication (fast, no AI)
  2. Claude: semantic dedup + day-trader relevance filtering + clean summaries
  3. Returns structured output ready for renderer.py

Claude receives all raw articles in one batched prompt and returns JSON.
"""
import hashlib
import json
import re
from datetime import datetime

import anthropic
import pytz

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

# ── Output schema returned by this module ────────────────────────────────────
# {
#   "section1": {
#     "themes": [{"title": str, "thesis": str, "score": int}],
#     "articles": [Article]
#   },
#   "section2": {
#     "mag7": {
#       "AAPL": {"summary": str, "articles": [Article], "upgrades": [UpgradeRow]},
#       ...
#     }
#   },
#   "section3": {
#     "watchlist": {
#       "TICKER": {"summary": str, "articles": [Article], "upgrades": [UpgradeRow]},
#       ...
#     }
#   },
#   "section4": {
#     "summary": str,
#     "articles": [Article]
#   },
#   "deltaaone_available": bool,
# }


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _dedup_by_url(articles: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for a in articles:
        h = _url_hash(a.get("url", a.get("title", "")))
        if h not in seen:
            seen.add(h)
            out.append(a)
    return out


def _format_article_for_prompt(a: dict, idx: int) -> str:
    pub = a.get("published_at", "")
    if isinstance(pub, datetime):
        pub = pub.strftime("%Y-%m-%d %H:%M UTC")
    tickers = ", ".join(a.get("tickers", [])) or "none"
    return (
        f"[{idx}] SOURCE={a.get('source','')} | TICKERS={tickers} | TIME={pub}\n"
        f"TITLE: {a.get('title','')}\n"
        f"SUMMARY: {a.get('summary','')[:300]}\n"
    )


def _build_prompt(
    major_articles: list[dict],
    mag7_articles: list[dict],
    watchlist_articles: list[dict],
    other_articles: list[dict],
    mag7_tickers: list[str],
    watchlist_tickers: list[str],
    upgrades_mag7: list[dict],
    upgrades_watchlist: list[dict],
) -> str:
    sections = []

    if major_articles:
        lines = [_format_article_for_prompt(a, i) for i, a in enumerate(major_articles)]
        sections.append("## MAJOR NEWS POOL\n" + "\n".join(lines))

    if mag7_articles:
        lines = [_format_article_for_prompt(a, i) for i, a in enumerate(mag7_articles)]
        sections.append("## MAG7 NEWS POOL\nTickers: " + ", ".join(mag7_tickers) + "\n" + "\n".join(lines))

    if watchlist_articles:
        lines = [_format_article_for_prompt(a, i) for i, a in enumerate(watchlist_articles)]
        sections.append("## WATCHLIST NEWS POOL\nTickers: " + ", ".join(watchlist_tickers) + "\n" + "\n".join(lines))

    if other_articles:
        lines = [_format_article_for_prompt(a, i) for i, a in enumerate(other_articles)]
        sections.append("## OTHER NEWS POOL\n" + "\n".join(lines))

    raw_news = "\n\n".join(sections)

    upgrades_text = ""
    if upgrades_mag7 or upgrades_watchlist:
        rows = []
        for u in upgrades_mag7 + upgrades_watchlist:
            date_str = u["date"].strftime("%Y-%m-%d") if isinstance(u["date"], datetime) else str(u["date"])
            rows.append(f"{u['ticker']} | {u['firm']} | {u.get('from_grade','')} → {u.get('to_grade','')} | {u.get('action','')} | {date_str}")
        upgrades_text = "\n## ANALYST UPGRADES/DOWNGRADES\n" + "\n".join(rows)

    prompt = f"""You are a senior financial news editor preparing a pre-market briefing for a day trader.
Your job is to process the raw news below and produce a structured JSON output.

RULES:
1. DEDUPLICATION: Multiple articles covering the same event from different outlets → keep only the best one (most informative title/summary). Drop the rest.
2. RELEVANCE FILTER — only keep articles that are:
   - Time-sensitive and actionable TODAY for a day trader
   - Signal-generating: earnings results/guidance, Fed/macro data releases, analyst upgrades/downgrades, M&A, regulatory actions, product launches with market impact, major executive changes, pre-market movers
   - DROP: opinion pieces, market recaps/roundups, evergreen educational content, generic "here's what happened last week" articles
3. CLEAN SUMMARIES: For each surviving article, write a crisp 1-2 sentence summary focused on the trading implication.
4. SECTION 1 THEMES: After processing major news, synthesize the 1-3 most impactful macro trading themes for today.

{raw_news}
{upgrades_text}

Respond ONLY with valid JSON matching this exact schema (no markdown, no explanation):
{{
  "section1": {{
    "themes": [
      {{"title": "...", "thesis": "2-sentence trading thesis here", "score": 8}}
    ],
    "articles": [
      {{"title": "...", "summary": "...", "url": "...", "source": "...", "published_at": "...", "tickers": []}}
    ]
  }},
  "section2": {{
    "AAPL": {{"summary": "Overall situation for this ticker (or empty string if no news)", "articles": [{{"title": "...", "summary": "...", "url": "...", "source": "...", "published_at": "...", "tickers": ["AAPL"]}}]}},
    "MSFT": {{"summary": "", "articles": []}},
    "GOOGL": {{"summary": "", "articles": []}},
    "AMZN": {{"summary": "", "articles": []}},
    "META": {{"summary": "", "articles": []}},
    "NVDA": {{"summary": "", "articles": []}},
    "TSLA": {{"summary": "", "articles": []}}
  }},
  "section3": {{
    "TICKER": {{"summary": "...", "articles": []}}
  }},
  "section4": {{
    "summary": "Brief digest of remaining notable items",
    "articles": [
      {{"title": "...", "summary": "...", "url": "...", "source": "...", "published_at": "...", "tickers": []}}
    ]
  }}
}}

For section3, only include tickers that have relevant news. Omit silent tickers entirely.
If there are no themes/articles for a section, return empty arrays/objects.
"""
    return prompt


def run_editorial_pipeline(
    major_articles: list[dict],
    mag7_articles: list[dict],
    watchlist_articles: list[dict],
    other_articles: list[dict],
    mag7_tickers: list[str],
    watchlist_tickers: list[str],
    upgrades_mag7: list[dict],
    upgrades_watchlist: list[dict],
    deltaaone_available: bool = False,
) -> dict:
    """
    Main entry point. Runs URL dedup then calls Claude for the full editorial pass.
    Returns structured dict for renderer.py.
    """
    # Stage 1: URL dedup
    major_articles = _dedup_by_url(major_articles)
    mag7_articles = _dedup_by_url(mag7_articles)
    watchlist_articles = _dedup_by_url(watchlist_articles)
    other_articles = _dedup_by_url(other_articles)

    # Fallback result (used if Claude is unavailable)
    fallback = _build_fallback(
        major_articles, mag7_articles, watchlist_articles, other_articles,
        mag7_tickers, watchlist_tickers, upgrades_mag7, upgrades_watchlist,
        deltaaone_available,
    )

    if not ANTHROPIC_API_KEY:
        fallback["_claude_unavailable"] = True
        return fallback

    prompt = _build_prompt(
        major_articles, mag7_articles, watchlist_articles, other_articles,
        mag7_tickers, watchlist_tickers, upgrades_mag7, upgrades_watchlist,
    )

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = message.content[0].text.strip()

        # Strip markdown code fences if present
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

        result = json.loads(raw_text)
        result["upgrades_mag7"] = upgrades_mag7
        result["upgrades_watchlist"] = upgrades_watchlist
        result["deltaaone_available"] = deltaaone_available
        result["_claude_unavailable"] = False
        return result

    except json.JSONDecodeError:
        fallback["_claude_unavailable"] = True
        fallback["_error"] = "Claude returned invalid JSON"
        return fallback
    except Exception as e:
        fallback["_claude_unavailable"] = True
        fallback["_error"] = str(e)
        return fallback


def _build_fallback(
    major, mag7, watchlist, other,
    mag7_tickers, watchlist_tickers,
    upgrades_mag7, upgrades_watchlist,
    deltaaone_available,
) -> dict:
    """Fallback structure when Claude is unavailable — raw headlines, no filtering."""

    def _raw_articles(articles):
        return [
            {
                "title": a.get("title", ""),
                "summary": a.get("summary", ""),
                "url": a.get("url", ""),
                "source": a.get("source", ""),
                "published_at": a.get("published_at", "").isoformat() if isinstance(a.get("published_at"), datetime) else str(a.get("published_at", "")),
                "tickers": a.get("tickers", []),
            }
            for a in articles
        ]

    section2 = {t: {"summary": "", "articles": []} for t in mag7_tickers}
    for a in mag7:
        for t in (a.get("tickers") or []):
            if t in section2:
                section2[t]["articles"].append(_raw_articles([a])[0])

    section3 = {}
    for a in watchlist:
        for t in (a.get("tickers") or []):
            if t not in section3:
                section3[t] = {"summary": "", "articles": []}
            section3[t]["articles"].append(_raw_articles([a])[0])

    return {
        "section1": {"themes": [], "articles": _raw_articles(major)},
        "section2": section2,
        "section3": section3,
        "section4": {"summary": "", "articles": _raw_articles(other)},
        "upgrades_mag7": upgrades_mag7,
        "upgrades_watchlist": upgrades_watchlist,
        "deltaaone_available": deltaaone_available,
    }
