"""Per-trade journal, skipped-signal log, runs.csv, and performance_db.json.

All bot-generated, no Claude involvement. File formats are kept stable
across runs so history stays comparable day to day.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from trader.config import Paths
from trader.models import ExitReason

logger = logging.getLogger("trader.journal")


@dataclass
class TradeRecord:
    time: str
    ticker: str
    side: str
    qty: float
    fill_price: float
    pattern: str
    pattern_candle_timestamps: list[str]
    stop: float
    target: float
    exit_price: float | None
    exit_time: str | None
    exit_reason: str | None
    pnl_dollars: float | None
    pnl_pct: float | None
    simulated: bool


@dataclass
class SkipRecord:
    time: str
    ticker: str
    reason: str
    details: str = ""


class Journal:
    def __init__(self, paths: Paths, run_date: date):
        self.paths = paths
        self.run_date = run_date
        self.paths.ensure()

    def _trades_path(self) -> Path:
        return self.paths.journal_dir / f"{self.run_date.isoformat()}-trades.json"

    def _skips_path(self) -> Path:
        return self.paths.journal_dir / f"{self.run_date.isoformat()}-skips.json"

    def record_trade(self, trade: TradeRecord) -> None:
        path = self._trades_path()
        trades = self._read_json_list(path)
        trades.append(asdict(trade))
        self._write_json_list(path, trades)
        if trade.exit_reason is not None:
            self._update_performance_db(trade)
        logger.info(
            "Trade journaled: %s %s qty=%s pattern=%s exit_reason=%s pnl=%s",
            trade.side, trade.ticker, trade.qty, trade.pattern, trade.exit_reason, trade.pnl_dollars,
        )

    def record_skip(self, ticker: str, reason: str, details: str = "") -> None:
        path = self._skips_path()
        skips = self._read_json_list(path)
        skips.append(asdict(SkipRecord(time=datetime.now().isoformat(), ticker=ticker, reason=reason, details=details)))
        self._write_json_list(path, skips)

    def skip_reason_counts(self) -> dict[str, int]:
        skips = self._read_json_list(self._skips_path())
        counts: dict[str, int] = {}
        for s in skips:
            counts[s["reason"]] = counts.get(s["reason"], 0) + 1
        return counts

    def read_trades(self) -> list[dict[str, Any]]:
        return self._read_json_list(self._trades_path())

    def append_run_summary(self, mode: str, result: str, claude_cost_usd: float, pnl_dollars: float) -> None:
        path = self.paths.runs_csv
        is_new = not path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if is_new:
                writer.writerow(["date", "mode", "result", "claude_call_cost_usd", "pnl_usd"])
            writer.writerow([self.run_date.isoformat(), mode, result, f"{claude_cost_usd:.4f}", f"{pnl_dollars:.2f}"])

    def _update_performance_db(self, trade: TradeRecord) -> None:
        db = self._read_performance_db()
        is_win = (trade.pnl_dollars or 0.0) > 0

        ticker_stats = db["tickers"].setdefault(
            trade.ticker, {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0}
        )
        ticker_stats["trades"] += 1
        ticker_stats["wins" if is_win else "losses"] += 1
        ticker_stats["total_pnl"] += trade.pnl_dollars or 0.0

        pattern_stats = db["patterns"].setdefault(
            trade.pattern, {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0}
        )
        pattern_stats["trades"] += 1
        pattern_stats["wins" if is_win else "losses"] += 1
        pattern_stats["total_pnl"] += trade.pnl_dollars or 0.0

        self._write_performance_db(db)

    def _read_performance_db(self) -> dict[str, Any]:
        path = self.paths.performance_db
        if not path.exists():
            return {"tickers": {}, "patterns": {}}
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _write_performance_db(self, db: dict[str, Any]) -> None:
        path = self.paths.performance_db
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(db, fh, indent=2, sort_keys=True)

    def read_performance_db(self) -> dict[str, Any]:
        return self._read_performance_db()

    @staticmethod
    def _read_json_list(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    @staticmethod
    def _write_json_list(path: Path, data: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
