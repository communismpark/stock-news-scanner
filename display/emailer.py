"""
emailer.py — Build an HTML pre-market briefing and send it via SMTP.

Activated automatically when EMAIL_FROM / EMAIL_TO / EMAIL_PASSWORD are set in .env.
Uses Gmail by default; override EMAIL_SMTP_HOST / EMAIL_SMTP_PORT for other providers.
"""
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytz

from config import EMAIL_FROM, EMAIL_PASSWORD, EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_TO

ET = pytz.timezone("America/New_York")


def _safe(text: str) -> str:
    if not text:
        return ""
    return text.encode("ascii", errors="replace").decode("ascii")


def _to_et(dt) -> str:
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return str(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc)
    return dt.astimezone(ET).strftime("%I:%M %p ET")


def _article_html(article: dict, color: str) -> str:
    title = _safe(article.get("title", ""))
    source = _safe(article.get("source", ""))
    pub = _to_et(article.get("published_at", ""))
    summary = _safe(article.get("summary", ""))
    url = article.get("url", "")
    tickers = " ".join(f"${t}" for t in article.get("tickers", []))

    link = f'<a href="{url}" style="color:{color};text-decoration:none">{title}</a>' if url else title
    ticker_html = (
        f'<div style="color:#00bcd4;font-size:12px;margin-top:4px">{tickers}</div>'
        if tickers else ""
    )
    return (
        f'<div style="border-left:3px solid {color};padding:8px 12px;margin:6px 0;background:#1a1a1a">'
        f'<div style="font-weight:bold;font-size:14px">{link}</div>'
        f'<div style="color:#888;font-size:11px">{source} · {pub}</div>'
        f'<div style="color:#ccc;font-size:13px;margin-top:4px">{summary}</div>'
        f'{ticker_html}'
        f'</div>'
    )


def _upgrades_html(upgrades: list[dict]) -> str:
    if not upgrades:
        return ""
    rows = ""
    for u in upgrades:
        action = u.get("action", "")
        if action.lower() in ("upgrade", "init", "reiterated"):
            action_color = "#4caf50"
        elif action.lower() == "downgrade":
            action_color = "#f44336"
        else:
            action_color = "#ff9800"
        date_str = (
            u["date"].strftime("%b %d")
            if isinstance(u["date"], datetime)
            else str(u.get("date", ""))
        )
        rows += (
            f'<tr>'
            f'<td style="padding:4px 8px;font-weight:bold">{u.get("ticker","")}</td>'
            f'<td style="padding:4px 8px">{u.get("firm","")}</td>'
            f'<td style="padding:4px 8px">{u.get("from_grade","") or "-"}</td>'
            f'<td style="padding:4px 8px">{u.get("to_grade","") or "-"}</td>'
            f'<td style="padding:4px 8px;color:{action_color}">{action}</td>'
            f'<td style="padding:4px 8px;color:#888">{date_str}</td>'
            f'</tr>'
        )
    return (
        '<table style="border-collapse:collapse;width:100%;margin:8px 0;font-size:13px">'
        '<tr style="color:#00bcd4;border-bottom:1px solid #333">'
        '<th style="padding:4px 8px;text-align:left">Ticker</th>'
        '<th style="padding:4px 8px;text-align:left">Firm</th>'
        '<th style="padding:4px 8px;text-align:left">From</th>'
        '<th style="padding:4px 8px;text-align:left">To</th>'
        '<th style="padding:4px 8px;text-align:left">Action</th>'
        '<th style="padding:4px 8px;text-align:left">Date</th>'
        '</tr>'
        f'{rows}'
        '</table>'
    )


def build_html(result: dict, window_start: datetime, window_end: datetime) -> str:
    start_str = window_start.astimezone(ET).strftime("%b %d %I:%M %p ET")
    end_str = window_end.astimezone(ET).strftime("%b %d %I:%M %p ET")
    today = datetime.now(ET).strftime("%A, %B %d, %Y")

    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        '<body style="background:#111;color:#eee;font-family:monospace;padding:20px;max-width:900px;margin:0 auto">'
        f'<h1 style="color:#fff;border-bottom:2px solid #fff;padding-bottom:8px">'
        f'STOCK NEWS SCANNER — {today}</h1>'
        f'<p style="color:#888;font-size:12px">{start_str} → {end_str}</p>'
    )

    # ── Section 1 ────────────────────────────────────────────────────────────
    s1 = result.get("section1", {})
    html += '<h2 style="color:#f44336;border-bottom:1px solid #f44336">SECTION 1 — MAJOR NEWS &amp; TRADING THESIS</h2>'
    for theme in s1.get("themes", []):
        score = theme.get("score", 0)
        score_color = "#4caf50" if score >= 7 else ("#ff9800" if score >= 4 else "#888")
        html += (
            '<div style="border:1px solid #f44336;padding:10px 14px;margin:8px 0;background:#1a0000">'
            f'<div style="font-weight:bold;font-size:15px">{_safe(theme.get("title",""))}'
            f' <span style="color:{score_color};font-size:12px">[Signal {score}/10]</span></div>'
            f'<div style="color:#ccc;margin-top:6px">{_safe(theme.get("thesis",""))}</div>'
            '</div>'
        )
    for article in s1.get("articles", []):
        html += _article_html(article, "#ff9800")

    # ── Section 2 ────────────────────────────────────────────────────────────
    s2 = result.get("section2", {})
    html += '<h2 style="color:#2196f3;border-bottom:1px solid #2196f3">SECTION 2 — MAG 7</h2>'
    html += _upgrades_html(result.get("upgrades_mag7", []))
    for ticker, data in s2.items():
        articles = data.get("articles", [])
        summary = data.get("summary", "")
        if not articles and not summary:
            continue
        html += f'<h3 style="color:#2196f3;margin-top:16px">${ticker}</h3>'
        if summary:
            html += f'<p style="color:#ccc">{_safe(summary)}</p>'
        for article in articles:
            html += _article_html(article, "#2196f3")

    # ── Section 3 ────────────────────────────────────────────────────────────
    s3 = result.get("section3", {})
    html += '<h2 style="color:#4caf50;border-bottom:1px solid #4caf50">SECTION 3 — WATCHLIST</h2>'
    html += _upgrades_html(result.get("upgrades_watchlist", []))
    for ticker, data in s3.items():
        articles = data.get("articles", [])
        summary = data.get("summary", "")
        if not articles and not summary:
            continue
        html += f'<h3 style="color:#4caf50;margin-top:16px">${ticker}</h3>'
        if summary:
            html += f'<p style="color:#ccc">{_safe(summary)}</p>'
        for article in articles:
            html += _article_html(article, "#4caf50")

    # ── Section 4 ────────────────────────────────────────────────────────────
    s4 = result.get("section4", {})
    html += '<h2 style="color:#888;border-bottom:1px solid #555">SECTION 4 — OTHER NOTABLE NEWS</h2>'
    if s4.get("summary"):
        html += f'<p style="color:#aaa">{_safe(s4["summary"])}</p>'
    for article in s4.get("articles", []):
        html += _article_html(article, "#888")

    html += (
        '<hr style="border-color:#333;margin-top:24px">'
        '<p style="color:#555;font-size:11px">End of briefing</p>'
        '</body></html>'
    )
    return html


def send_briefing(result: dict, window_start: datetime, window_end: datetime) -> bool:
    """Send the HTML briefing via SMTP. Returns True on success, False if not configured."""
    if not all([EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD]):
        return False

    today = datetime.now(ET).strftime("%b %d, %Y")
    subject = f"Pre-Market Briefing — {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(build_html(result, window_start, window_end), "html"))

    with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(EMAIL_FROM, EMAIL_PASSWORD)
        smtp.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

    return True
