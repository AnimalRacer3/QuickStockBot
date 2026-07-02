"""End-of-day report generation (Markdown). Bot-generated only, no Claude."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from trader.journal import Journal
from trader.models import WatchlistEntry


@dataclass
class DailyReportInputs:
    run_date: date
    mode: str
    starting_equity: float
    ending_equity: float
    watchlist: list[WatchlistEntry]
    claude_cost_usd: float
    claude_notes: str
    zero_trade_day: bool
    zero_trade_reason: str = ""
    screen_summary: str = ""


def _pnl_pct(starting: float, ending: float) -> float:
    if starting <= 0:
        return 0.0
    return (ending - starting) / starting * 100.0


def build_report(inputs: DailyReportInputs, journal: Journal) -> str:
    trades = journal.read_trades()
    skip_counts = journal.skip_reason_counts()
    perf_db = journal.read_performance_db()

    pnl_dollars = inputs.ending_equity - inputs.starting_equity
    pnl_pct = _pnl_pct(inputs.starting_equity, inputs.ending_equity)

    lines: list[str] = []
    lines.append(f"# Daily Report: {inputs.run_date.isoformat()}")
    lines.append("")
    lines.append(f"**Mode:** {inputs.mode}")
    lines.append(
        f"**P&L:** ${pnl_dollars:,.2f} ({pnl_pct:+.2f}%) | "
        f"Starting equity: ${inputs.starting_equity:,.2f} | Ending equity: ${inputs.ending_equity:,.2f}"
    )
    lines.append(f"**Claude call cost:** ${inputs.claude_cost_usd:.4f}")
    lines.append("")

    if inputs.zero_trade_day:
        lines.append("## Zero-Trade Day")
        lines.append("")
        lines.append(inputs.zero_trade_reason or "No trades were taken today.")
        lines.append("")
        if inputs.screen_summary:
            lines.append("### Mechanical Screen Results")
            lines.append("")
            lines.append(inputs.screen_summary)
            lines.append("")

    lines.append("## Watchlist")
    lines.append("")
    if inputs.watchlist:
        lines.append("| Rank | Ticker | Reason | Catalyst |")
        lines.append("|---|---|---|---|")
        for entry in inputs.watchlist:
            lines.append(f"| {entry.rank} | {entry.ticker} | {entry.reason} | {entry.catalyst} |")
    else:
        lines.append("_No watchlist tickers today._")
    lines.append("")

    lines.append("## Claude Notes")
    lines.append("")
    lines.append(inputs.claude_notes or "_none_")
    lines.append("")

    lines.append("## Trades")
    lines.append("")
    if trades:
        lines.append("| Time | Ticker | Side | Qty | Fill | Pattern | Exit | Exit Reason | P&L $ | P&L % |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for t in trades:
            pnl_d = t.get("pnl_dollars")
            pnl_p = t.get("pnl_pct")
            pnl_d_str = f"{pnl_d:.2f}" if pnl_d is not None else ""
            pnl_p_str = f"{pnl_p:.2f}" if pnl_p is not None else ""
            lines.append(
                f"| {t['time']} | {t['ticker']} | {t['side']} | {t['qty']} | {t['fill_price']:.2f} | "
                f"{t['pattern']} | {t.get('exit_price') or ''} | {t.get('exit_reason') or ''} | "
                f"{pnl_d_str} | {pnl_p_str} |"
            )
    else:
        lines.append("_No trades today._")
    lines.append("")

    lines.append("## Skip Reasons")
    lines.append("")
    if skip_counts:
        lines.append("| Reason | Count |")
        lines.append("|---|---|")
        for reason, count in sorted(skip_counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("_No skipped signals recorded._")
    lines.append("")

    lines.append("## Proven Performers (performance_db)")
    lines.append("")
    top_tickers = sorted(perf_db.get("tickers", {}).items(), key=lambda kv: -kv[1]["total_pnl"])[:10]
    if top_tickers:
        lines.append("| Ticker | Trades | Wins | Losses | Total P&L |")
        lines.append("|---|---|---|---|---|")
        for ticker, stats in top_tickers:
            lines.append(f"| {ticker} | {stats['trades']} | {stats['wins']} | {stats['losses']} | {stats['total_pnl']:.2f} |")
    else:
        lines.append("_No historical performance data yet._")
    lines.append("")

    top_patterns = sorted(perf_db.get("patterns", {}).items(), key=lambda kv: -kv[1]["total_pnl"])
    if top_patterns:
        lines.append("### By Pattern")
        lines.append("")
        lines.append("| Pattern | Trades | Wins | Losses | Total P&L |")
        lines.append("|---|---|---|---|---|")
        for pattern, stats in top_patterns:
            lines.append(f"| {pattern} | {stats['trades']} | {stats['wins']} | {stats['losses']} | {stats['total_pnl']:.2f} |")
        lines.append("")

    return "\n".join(lines)


def save_report(reports_dir: Path, run_date: date, content: str) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{run_date.isoformat()}-report.md"
    path.write_text(content, encoding="utf-8")
    return path
