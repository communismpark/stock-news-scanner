"""
renderer.py — Rich terminal display for the 4-section stock news scanner.
"""
import sys
from datetime import datetime

import pytz
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich import box

# Force non-legacy mode so Rich uses ANSI codes instead of Win32 API,
# which avoids GBK encoding failures on Chinese-locale Windows machines.
console = Console(highlight=False, legacy_windows=False)


def _safe(text: str) -> str:
    """Replace characters that Windows GBK codec can't handle."""
    if not text:
        return ""
    return text.encode("ascii", errors="replace").decode("ascii")
ET = pytz.timezone("America/New_York")


def _to_et(dt) -> str:
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc)
    return dt.astimezone(ET).strftime("%I:%M %p ET")


def _article_panel(article: dict, color: str = "white") -> Panel:
    source = _safe(article.get("source", ""))
    pub = _to_et(article.get("published_at", ""))
    tickers = " ".join(f"[bold cyan]${t}[/]" for t in article.get("tickers", []))
    summary = _safe(article.get("summary", ""))
    url = _safe(article.get("url", ""))

    body = f"[{color}]{summary}[/]"
    if tickers:
        body += f"\n{tickers}"
    if url:
        body += f"\n[dim]{url}[/]"

    title = f"[bold]{_safe(article.get('title', ''))}[/]  [dim]{source} · {pub}[/]"
    return Panel(body, title=title, border_style=color, padding=(0, 1))


def render_warning(message: str):
    console.print(f"\n[bold yellow]WARNING: {message}[/]\n")


def render_header(window_start: datetime, window_end: datetime):
    start_str = window_start.astimezone(ET).strftime("%b %d %I:%M %p ET")
    end_str = window_end.astimezone(ET).strftime("%b %d %I:%M %p ET")
    console.print()
    console.print(Rule(
        f"[bold white] STOCK NEWS SCANNER  |  {start_str} -> {end_str} [/]",
        style="bright_white",
    ))
    console.print()


def render_section1(data: dict):
    console.print(Rule("[bold red] SECTION 1 -- MAJOR NEWS & TRADING THESIS [/]", style="red"))
    console.print()

    themes = data.get("themes", [])
    if themes:
        for theme in themes:
            score = theme.get("score", 0)
            score_color = "green" if score >= 7 else ("yellow" if score >= 4 else "dim")
            title_text = Text()
            title_text.append(f"  {_safe(theme.get('title', ''))}  ", style="bold white")
            title_text.append(f"[Signal {score}/10]", style=f"bold {score_color}")
            console.print(Panel(
                f"[white]{_safe(theme.get('thesis', ''))}[/]",
                title=title_text,
                border_style="red",
                padding=(0, 2),
            ))
        console.print()

    articles = data.get("articles", [])
    if not articles and not themes:
        console.print("[dim]  No major news in this window.[/]\n")
        return

    for article in articles:
        console.print(_article_panel(article, color="yellow"))

    console.print()


def render_section2(data: dict, upgrades: list[dict]):
    console.print(Rule("[bold blue] SECTION 2 -- MAG 7 [/]", style="blue"))
    console.print()

    # Upgrades/downgrades table for mag7
    mag7_tickers = {"AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"}
    mag7_upgrades = [u for u in upgrades if u.get("ticker", "") in mag7_tickers]
    if mag7_upgrades:
        _render_upgrades_table(mag7_upgrades)

    any_content = False
    for ticker, ticker_data in data.items():
        articles = ticker_data.get("articles", [])
        summary = ticker_data.get("summary", "")
        if not articles and not summary:
            continue
        any_content = True
        console.print(f"[bold blue]  ${ticker}[/]")
        if summary:
            console.print(f"  [white]{_safe(summary)}[/]\n")
        for article in articles:
            console.print(_article_panel(article, color="blue"))

    if not any_content and not mag7_upgrades:
        console.print("[dim]  No Mag 7 news in this window.[/]")

    console.print()


def render_section3(data: dict, upgrades: list[dict]):
    console.print(Rule("[bold green] SECTION 3 -- WATCHLIST [/]", style="green"))
    console.print()

    watchlist_tickers = set(data.keys())
    wl_upgrades = [u for u in upgrades if u.get("ticker", "") in watchlist_tickers]
    if wl_upgrades:
        _render_upgrades_table(wl_upgrades)

    if not data and not wl_upgrades:
        console.print("[dim]  No watchlist news in this window.[/]")
        console.print()
        return

    for ticker, ticker_data in data.items():
        articles = ticker_data.get("articles", [])
        summary = ticker_data.get("summary", "")
        if not articles and not summary:
            continue
        console.print(f"[bold green]  ${ticker}[/]")
        if summary:
            console.print(f"  [white]{_safe(summary)}[/]\n")
        for article in articles:
            console.print(_article_panel(article, color="green"))

    console.print()


def render_section4(data: dict, deltaaone_available: bool):
    console.print(Rule("[bold dim] SECTION 4 -- OTHER NOTABLE NEWS [/]", style="dim"))

    console.print()

    if not deltaaone_available:
        console.print("[dim]  @DeItaone (Nitter) unavailable -- showing RSS/API sources only.[/]\n")

    summary = data.get("summary", "")
    if summary:
        console.print(Panel(f"[dim white]{_safe(summary)}[/]", border_style="dim", padding=(0, 2)))
        console.print()

    articles = data.get("articles", [])
    if not articles and not summary:
        console.print("[dim]  No other notable news.[/]")
        console.print()
        return

    for article in articles:
        console.print(_article_panel(article, color="white"))

    console.print()


def _render_upgrades_table(upgrades: list[dict]):
    table = Table(
        "Ticker", "Firm", "From", "To", "Action", "Date",
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    for u in upgrades:
        action = u.get("action", "")
        action_color = (
            "green" if action.lower() in ("upgrade", "init", "reiterated")
            else "red" if action.lower() == "downgrade"
            else "yellow"
        )
        date_str = u["date"].strftime("%b %d") if isinstance(u["date"], datetime) else str(u.get("date", ""))
        table.add_row(
            f"[bold]{u.get('ticker', '')}[/]",
            u.get("firm", ""),
            u.get("from_grade", "") or "-",
            u.get("to_grade", "") or "-",
            f"[{action_color}]{action}[/]",
            date_str,
        )
    console.print(table)
    console.print()


def render_all(result: dict, window_start: datetime, window_end: datetime):
    """Main render function — renders all 4 sections from editor.py output."""
    render_header(window_start, window_end)

    if result.get("_claude_unavailable"):
        err = result.get("_error", "")
        msg = "Claude API unavailable — showing raw headlines without AI filtering."
        if err:
            msg += f" ({err})"
        render_warning(msg)

    render_section1(result.get("section1", {}))
    render_section2(
        result.get("section2", {}),
        result.get("upgrades_mag7", []),
    )
    render_section3(
        result.get("section3", {}),
        result.get("upgrades_watchlist", []),
    )
    render_section4(
        result.get("section4", {}),
        result.get("deltaaone_available", False),
    )

    console.print(Rule("[dim]End of briefing[/]", style="dim"))
    console.print()
