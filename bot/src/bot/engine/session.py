from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Protocol

from bot.alpaca.client import MarketClient
from bot.engine.circuit_breaker import DailyAction, DailyState, check_daily_limits
from bot.engine.config import ExecutionConfig
from bot.engine.exits import (
    ExitSignal,
    OpenPosition,
    check_take_profit,
    check_trailing_stop,
    dump_exit,
    trail_off_candle_pattern,
    trail_off_per_candle,
    update_high_water_mark,
)
from bot.engine.gate import check_entry_gate
from bot.engine.sizing import compute_shares
from bot.models import (
    AccountSnapshot,
    Bar,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)
from bot.ta.config import TAConfig
from bot.ta.helpers import high_of_day, low_of_day
from bot.ta.macd import classify_macd
from bot.ta.models import MacdState
from bot.ta.patterns import run_enabled_patterns
from bot.ta.scoring import compute_score

logger = logging.getLogger(__name__)


class Clock(Protocol):
    """Mockable clock interface."""

    def now(self) -> datetime: ...
    def session_open(self) -> datetime: ...
    def is_market_open(self) -> bool: ...
    def is_near_close(self) -> bool: ...


class WallClock:
    """Live wall-clock implementation."""

    def __init__(self, session_open_time: datetime, close_time: datetime) -> None:
        self._open = session_open_time
        self._close = close_time

    def now(self) -> datetime:
        return datetime.now(tz=timezone.utc)

    def session_open(self) -> datetime:
        return self._open

    def is_market_open(self) -> bool:
        n = self.now()
        return self._open <= n < self._close

    def is_near_close(self) -> bool:
        n = self.now()
        from datetime import timedelta
        return n >= self._close - timedelta(minutes=5)


@dataclass
class CandleSignal:
    """Per-symbol signals computed on each candle."""
    symbol: str
    bars: list[Bar]
    macd: MacdState
    pattern_tags: list[str]
    score: float
    price: float
    vwap_val: float


@dataclass
class TradeRecord:
    """In-memory record of an executed trade."""
    symbol: str
    entry_order: Order
    entry_price: float
    shares: int
    position: OpenPosition
    exit_orders: list[Order] = field(default_factory=list)
    realized_pnl: float = 0.0
    prev_pattern_tags: list[str] = field(default_factory=list)


@dataclass
class SessionResult:
    """Summary of a completed trading session."""
    trades_entered: int = 0
    trades_exited: int = 0
    realized_pnl: float = 0.0
    halted: bool = False
    halt_reason: str = ""
    orders_submitted: list[Order] = field(default_factory=list)
    log_messages: list[str] = field(default_factory=list)
    goalpost_trade_count: int = 1


class ExecutionSession:
    """
    Single-day execution engine.

    Deterministic and mockable — inject a MarketClient and a Clock.
    Call run_cycle() once per candle to process entries/exits.
    """

    def __init__(
        self,
        client: MarketClient,
        clock: Clock,
        config: ExecutionConfig,
        ta_config: TAConfig | None = None,
        # ML conviction stub — returns score_setup in [0, 1]
        score_setup_fn: Callable[[str, list[Bar]], float] | None = None,
    ) -> None:
        self._client = client
        self._clock = clock
        self._cfg = config
        self._ta_cfg = ta_config or TAConfig()
        self._score_setup_fn = score_setup_fn or (lambda sym, bars: 1.0)

        self._daily_state: DailyState | None = None
        self._open_trades: dict[str, TradeRecord] = {}  # symbol → TradeRecord
        self._result = SessionResult(
            goalpost_trade_count=config.goalpost_trade_count()
        )
        self._z_cutoff_passed = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_day(self) -> None:
        """Snapshot account equity at the start of the day."""
        acct = self._client.get_account()
        self._daily_state = DailyState(
            day_start_equity=float(acct.equity),
            goalpost_trade_count=self._cfg.goalpost_trade_count(),
        )
        self._log_margin_notice(acct)
        self._log(
            f"Day started: equity={acct.equity}, "
            f"buying_power={acct.buying_power}, "
            f"goalpost_trades={self._daily_state.goalpost_trade_count}"
        )

    def run_cycle(
        self,
        ranked_symbols: list[str],
        bars_by_symbol: dict[str, list[Bar]],
    ) -> SessionResult:
        """
        Process one candle cycle over the ranked watchlist.

        ranked_symbols: top-N tradable leaders from the scanner, ordered by rank.
        bars_by_symbol: intraday bars (all candles so far today) per symbol.
        """
        assert self._daily_state is not None, "call start_day() first"

        if not self._clock.is_market_open():
            return self._result

        # Z-hour cutoff: no entries within the first z_hour_cutoff hours
        elapsed_hours = self._hours_since_open()
        if elapsed_hours < self._cfg.z_hour_cutoff:
            self._log(
                f"z-hour cutoff active ({elapsed_hours:.2f}h < {self._cfg.z_hour_cutoff}h); "
                "no entries this cycle"
            )
            # Still process exits for existing positions
            self._process_exits(bars_by_symbol)
            return self._result

        if not self._z_cutoff_passed:
            self._z_cutoff_passed = True

        # Update circuit breakers
        action = self._refresh_circuit_breakers()
        if action == DailyAction.FLATTEN_AND_HALT:
            self._flatten_all(reason=self._daily_state.halt_reason)
            return self._result
        if action == DailyAction.HALT:
            self._process_exits(bars_by_symbol)
            return self._result

        # Force-close near end of day
        if self._cfg.force_close_at_close and self._clock.is_near_close():
            self._flatten_all(reason="force_close_at_close")
            return self._result

        # Process exits first, then look for new entries
        self._process_exits(bars_by_symbol)

        if not self._daily_state.halted:
            self._process_entries(ranked_symbols, bars_by_symbol)

        return self._result

    def end_day(self) -> SessionResult:
        """Force-close any remaining positions and return the session result."""
        if self._open_trades:
            self._flatten_all(reason="end_day")
        self._result.halted = self._daily_state.halted if self._daily_state else False
        self._result.halt_reason = (
            self._daily_state.halt_reason if self._daily_state else ""
        )
        return self._result

    # ------------------------------------------------------------------
    # Internal: entries
    # ------------------------------------------------------------------

    def _process_entries(
        self,
        ranked_symbols: list[str],
        bars_by_symbol: dict[str, list[Bar]],
    ) -> None:
        # Only consider the top-N tradable leaders
        candidates = ranked_symbols[: self._cfg.active_tickers_n]

        for symbol in candidates:
            if symbol in self._open_trades:
                continue  # already in a position
            bars = bars_by_symbol.get(symbol, [])
            if len(bars) < 2:
                continue

            # Compute signals
            macd = classify_macd(bars, self._ta_cfg)
            pattern_matches = run_enabled_patterns(
                bars,
                self._ta_cfg.enabled_patterns,
                self._ta_cfg.pattern_candle_lookback,
            )
            pattern_tags = [m.tag for m in pattern_matches if m.matched]
            price = float(bars[-1].close)
            hod = high_of_day(bars)
            lod = low_of_day(bars)
            _, ta = compute_score(
                symbol=symbol,
                has_news=False,
                sentiment_score=0.0,
                macd_state=macd,
                pattern_matches=pattern_matches,
                price=price,
                high=hod,
                low=lod,
            )

            score_setup = self._score_setup_fn(symbol, bars)

            gate = check_entry_gate(
                bars=bars,
                macd=macd,
                pattern_tags=pattern_tags,
                score_setup=score_setup,
                enabled_patterns=self._ta_cfg.enabled_patterns,
                conviction_threshold=self._cfg.conviction_threshold,
                overextension_pct=self._cfg.overextension_pct,
            )

            if not gate.passed:
                self._log(f"SKIP {symbol}: {gate.reason}")
                continue

            # Check margin / PDT before sizing
            acct = self._client.get_account()
            if not self._margin_allows_entry(acct):
                self._log(f"SKIP {symbol}: margin/PDT check failed")
                continue

            sizing = compute_shares(
                equity=float(acct.equity),
                buying_power=float(acct.buying_power),
                entry_price=price,
                config=self._cfg,
            )

            if sizing.skipped:
                self._log(f"SKIP {symbol}: sizing skipped ({sizing.skip_reason})")
                continue

            # Submit entry order — log AFTER the Alpaca request
            entry_order = self._client.submit_order(
                symbol=symbol,
                qty=Decimal(str(sizing.shares)),
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                time_in_force=TimeInForce.DAY,
            )
            self._result.orders_submitted.append(entry_order)

            filled = self._client.poll_order(entry_order.id)
            if filled.status != OrderStatus.FILLED:
                self._log(
                    f"ENTRY {symbol}: order {entry_order.id} not filled "
                    f"(status={filled.status}); skipping"
                )
                continue

            fill_price = float(filled.filled_avg_price or Decimal(str(price)))
            position = OpenPosition(
                symbol=symbol,
                entry_price=fill_price,
                shares=sizing.shares,
                remaining_shares=sizing.shares,
                high_water_mark=fill_price,
                pattern_tags=pattern_tags[:],
            )
            trade = TradeRecord(
                symbol=symbol,
                entry_order=filled,
                entry_price=fill_price,
                shares=sizing.shares,
                position=position,
                prev_pattern_tags=pattern_tags[:],
            )
            self._open_trades[symbol] = trade
            self._result.trades_entered += 1
            self._log(
                f"ENTRY {symbol}: {sizing.shares} shares @ {fill_price:.2f} "
                f"(risk_pct={sizing.effective_risk_pct:.2f}%, "
                f"max_risk=${sizing.max_risk_dollars:.2f})"
            )

    # ------------------------------------------------------------------
    # Internal: exits
    # ------------------------------------------------------------------

    def _process_exits(self, bars_by_symbol: dict[str, list[Bar]]) -> None:
        closed = []
        bullish_tags = set(self._ta_cfg.enabled_patterns)

        for symbol, trade in self._open_trades.items():
            bars = bars_by_symbol.get(symbol, [])
            if not bars:
                continue

            price = float(bars[-1].close)
            pos = trade.position
            update_high_water_mark(pos, price)

            macd = classify_macd(bars, self._ta_cfg)
            pattern_matches = run_enabled_patterns(
                bars,
                self._ta_cfg.enabled_patterns,
                self._ta_cfg.pattern_candle_lookback,
            )
            pattern_tags = [m.tag for m in pattern_matches if m.matched]

            signal: ExitSignal | None = None

            # 1. Trailing stop (independent, highest priority after take-profit)
            if self._cfg.trailing_stop and check_trailing_stop(
                pos, price, self._cfg.trailing_stop_pct
            ):
                signal = dump_exit(pos, "trailing stop hit")

            # 2. Take-profit reached
            elif check_take_profit(pos, price, self._cfg.take_profit_pct):
                if self._cfg.exit_mode == "dump":
                    signal = dump_exit(pos, "take_profit reached (dump)")
                else:
                    # trail_off mode
                    if self._cfg.trail_off_trigger == "per_candle":
                        signal = trail_off_per_candle(
                            pos,
                            macd,
                            pattern_tags,
                            bullish_tags,
                            self._cfg.trail_off_fraction_per_candle,
                            reason="take_profit: trail_off per_candle",
                        )
                    else:
                        signal = trail_off_candle_pattern(
                            pos,
                            macd,
                            pattern_tags,
                            bullish_tags,
                            trade.prev_pattern_tags,
                            self._cfg.trail_off_fraction_per_candle,
                            reason="take_profit: trail_off candle_pattern",
                        )

            # 3. Topping / back-side detected — dump remainder
            else:
                from bot.engine.gate import _BEARISH_TAGS
                has_reversal = any(t in _BEARISH_TAGS for t in pattern_tags)
                is_backside = not macd.eligible or macd.slope <= 0

                if has_reversal or is_backside:
                    if self._cfg.exit_mode == "dump":
                        signal = dump_exit(pos, "reversal/back-side detected (dump)")
                    else:
                        # trail_off: dump remainder when bullishness ends
                        signal = trail_off_per_candle(
                            pos,
                            macd,
                            pattern_tags,
                            bullish_tags,
                            self._cfg.trail_off_fraction_per_candle,
                            reason="reversal/back-side: trail_off",
                        )

                # 4. In trail_off mode, keep scaling out each candle even without a new trigger
                elif self._cfg.exit_mode == "trail_off":
                    if self._cfg.trail_off_trigger == "per_candle":
                        signal = trail_off_per_candle(
                            pos,
                            macd,
                            pattern_tags,
                            bullish_tags,
                            self._cfg.trail_off_fraction_per_candle,
                            reason="trail_off per_candle ongoing",
                        )
                    else:
                        signal = trail_off_candle_pattern(
                            pos,
                            macd,
                            pattern_tags,
                            bullish_tags,
                            trade.prev_pattern_tags,
                            self._cfg.trail_off_fraction_per_candle,
                            reason="trail_off candle_pattern ongoing",
                        )

            trade.prev_pattern_tags = pattern_tags[:]

            if signal is None:
                continue

            self._execute_exit(trade, signal, price)

            if signal.is_final or pos.is_closed:
                closed.append(symbol)

        for sym in closed:
            del self._open_trades[sym]

    def _execute_exit(
        self, trade: TradeRecord, signal: ExitSignal, current_price: float
    ) -> None:
        pos = trade.position
        qty = min(signal.shares_to_sell, pos.remaining_shares)
        if qty <= 0:
            return

        exit_order = self._client.submit_order(
            symbol=signal.symbol,
            qty=Decimal(str(qty)),
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )
        self._result.orders_submitted.append(exit_order)

        filled = self._client.poll_order(exit_order.id)
        fill_price = float(filled.filled_avg_price or Decimal(str(current_price)))

        trade.exit_orders.append(filled)
        pos.remaining_shares -= qty

        chunk_pnl = (fill_price - trade.entry_price) * qty
        trade.realized_pnl += chunk_pnl
        self._result.realized_pnl += chunk_pnl

        if pos.is_closed or signal.is_final:
            self._result.trades_exited += 1
            self._log(
                f"EXIT {signal.symbol}: sold {qty} shares @ {fill_price:.2f} "
                f"({signal.reason}), pnl=${chunk_pnl:.2f}"
            )
        else:
            self._log(
                f"PARTIAL EXIT {signal.symbol}: sold {qty} of "
                f"{pos.remaining_shares + qty} shares @ {fill_price:.2f} "
                f"({signal.reason})"
            )

    def _flatten_all(self, reason: str) -> None:
        """Market-sell all remaining open positions."""
        symbols = list(self._open_trades.keys())
        for symbol in symbols:
            trade = self._open_trades[symbol]
            pos = trade.position
            if pos.remaining_shares > 0:
                signal = dump_exit(pos, reason)
                self._execute_exit(trade, signal, trade.entry_price)
        self._open_trades.clear()
        self._log(f"FLATTEN ALL: {reason}")

    # ------------------------------------------------------------------
    # Internal: margin / PDT
    # ------------------------------------------------------------------

    def _margin_allows_entry(self, acct: AccountSnapshot) -> bool:
        """
        Defer to Alpaca's reported buying_power / PDT state.

        Per the June 4 2026 framework: respect reported buying power and
        any lingering pattern_day_trader flag (broker not yet migrated).
        """
        if acct.is_pdt_restricted:
            self._log(
                "margin: PDT flag active — new entries blocked "
                "(old rule may still apply until broker migrates)"
            )
            return False
        if float(acct.buying_power) <= 0:
            return False
        # Intraday margin excess: daytrading_buying_power > 0 means intraday margin available
        if float(acct.day_trading_buying_power) < 0:
            self._log("margin: intraday margin deficit — skipping entry")
            return False
        return True

    def _log_margin_notice(self, acct: AccountSnapshot) -> None:
        equity = float(acct.equity)
        if equity < self._cfg.min_account_equity_notice:
            self._log(
                f"NOTICE: account equity ${equity:.2f} is below "
                f"min_account_equity_notice ${self._cfg.min_account_equity_notice:.2f}. "
                "Buying power is now intraday-margin-based; old $25k PDT rule may still "
                "apply until broker migrates."
            )

    # ------------------------------------------------------------------
    # Internal: utilities
    # ------------------------------------------------------------------

    def _refresh_circuit_breakers(self) -> DailyAction:
        assert self._daily_state is not None
        unrealized = self._compute_unrealized_pnl()
        action = check_daily_limits(
            self._daily_state,
            realized_pnl=self._result.realized_pnl,
            unrealized_pnl=unrealized,
            config=self._cfg,
        )
        if action != DailyAction.NONE:
            self._result.halted = True
            self._result.halt_reason = self._daily_state.halt_reason
        return action

    def _compute_unrealized_pnl(self) -> float:
        total = 0.0
        for trade in self._open_trades.values():
            pos = trade.position
            # Use entry_price as a placeholder when we have no live quote in tests
            total += (pos.high_water_mark - trade.entry_price) * pos.remaining_shares
        return total

    def _hours_since_open(self) -> float:
        now = self._clock.now()
        open_time = self._clock.session_open()
        delta = (now - open_time).total_seconds()
        return delta / 3600.0

    def _log(self, msg: str) -> None:
        logger.info(msg)
        self._result.log_messages.append(msg)
