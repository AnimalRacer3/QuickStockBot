"""The one Claude call of the day: 9:15 AM ticker selection.

The mechanical screen (price/RVOL/float/MACD) is pure Alpaca data and pure
code -- see `alpaca_data.AlpacaData.screen_premarket_gappers`. This module
takes those candidates, asks Claude (with the server-side web-search tool)
to verify each one's news catalyst and rank a shortlist, and parses the
response defensively into a `SelectionResult`.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trader.alpaca_data import AlpacaData, ScreenCandidate
from trader.models import WatchlistEntry

logger = logging.getLogger("trader.anthropic")

# Per-million-token USD pricing, used only for the cost line in the log.
# Approximate; not billing-accurate. Update if the configured model isn't listed.
_PRICING_PER_MTOK = {
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-opus-4-8": (5.00, 25.00),
}
_DEFAULT_PRICING = (3.00, 15.00)

_SYSTEM_PROMPT = """You are a disciplined day-trading research assistant. You will be given a \
table of pre-market gap candidates that already passed a mechanical screen (price range, \
relative volume, float, MACD). Your ONLY job is to verify each candidate has a real, \
current news catalyst (use web search) and rank the best ones.

Selection rules:
- A candidate qualifies only if it has a genuine, verifiable news catalyst from today or \
very recently (earnings, FDA news, contract win, upgrade/downgrade, M&A, guidance, etc.).
- Reject candidates with no discoverable catalyst, stale/old news, or purely technical \
("just gapped, no news") setups.
- Rank by conviction: catalyst strength + how well the mechanical stats support it.
- Return AT MOST {watchlist_size} tickers. Return FEWER, or an empty list, if fewer truly \
qualify. Do not pad the list to hit the count.
- If nothing qualifies, set "no_trade_day": true and return an empty watchlist.

Respond with STRICT JSON ONLY -- no markdown code fences, no commentary before or after. \
Exact schema:
{{"watchlist": [{{"ticker": "ABC", "reason": "...", "catalyst": "...", "rank": 1}}], \
"no_trade_day": false, "notes": "..."}}
"""


@dataclass
class SelectionResult:
    watchlist: list[WatchlistEntry]
    no_trade_day: bool
    notes: str
    raw_response: str
    cost_usd: float
    screen_candidates: list[ScreenCandidate] = field(default_factory=list)


class SelectionError(Exception):
    pass


def _candidate_table(candidates: list[ScreenCandidate]) -> str:
    lines = ["ticker,price,gap_pct,rvol,volume,float_millions,macd_bullish"]
    for c in candidates:
        d = c.to_dict()
        lines.append(
            f"{d['ticker']},{d['price']},{d['gap_pct']},{d['rvol']},"
            f"{d['volume']},{d['float_millions']},{d['macd_bullish']}"
        )
    return "\n".join(lines)


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def _extract_text(response: Any) -> str:
    return "".join(block.text for block in response.content if getattr(block, "type", None) == "text")


def _estimate_cost(response: Any, model: str) -> float:
    input_price, output_price = _PRICING_PER_MTOK.get(model, _DEFAULT_PRICING)
    usage = response.usage
    return (usage.input_tokens * input_price + usage.output_tokens * output_price) / 1_000_000.0


def _parse_and_validate(text: str, watchlist_size: int, alpaca: AlpacaData) -> tuple[list[WatchlistEntry], bool, str]:
    cleaned = _strip_json_fences(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SelectionError(f"malformed JSON: {exc}") from exc

    if not isinstance(data, dict) or "watchlist" not in data or "no_trade_day" not in data:
        raise SelectionError(f"response missing required keys: {data!r}")

    no_trade_day = bool(data["no_trade_day"])
    notes = str(data.get("notes", ""))
    raw_watchlist = data["watchlist"]
    if not isinstance(raw_watchlist, list):
        raise SelectionError("watchlist is not a list")

    entries: list[WatchlistEntry] = []
    for item in raw_watchlist[:watchlist_size]:
        if not isinstance(item, dict) or not all(k in item for k in ("ticker", "reason", "catalyst", "rank")):
            logger.warning("Dropping malformed watchlist entry: %r", item)
            continue
        ticker = str(item["ticker"]).upper().strip()
        if not alpaca.validate_ticker(ticker):
            logger.warning("Dropping %s: failed Alpaca ticker validation", ticker)
            continue
        entries.append(
            WatchlistEntry(
                ticker=ticker,
                reason=str(item["reason"]),
                catalyst=str(item["catalyst"]),
                rank=int(item["rank"]),
            )
        )
    entries.sort(key=lambda e: e.rank)
    return entries, no_trade_day, notes


def run_ticker_selection(
    anthropic_api_key: str,
    model: str,
    max_tokens: int,
    watchlist_size: int,
    candidates: list[ScreenCandidate],
    alpaca: AlpacaData,
    log_path: Path,
) -> SelectionResult:
    """Make the single daily Claude call and return a validated selection.

    Retries once on malformed/unparseable output. Never raises for a clean
    "no candidates qualify" answer -- only for two consecutive hard failures
    (API error or unparseable JSON both times), which the caller treats the
    same as a no-trade day.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    system = _SYSTEM_PROMPT.format(watchlist_size=watchlist_size)
    user_content = (
        f"Candidate screen results ({len(candidates)} passed mechanical filters):\n\n"
        f"{_candidate_table(candidates)}\n\n"
        "Verify catalysts with web search and return the STRICT JSON described in your instructions."
    )

    last_error: Exception | None = None
    total_cost = 0.0
    last_raw = ""

    for attempt in range(2):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": user_content}],
            )
            # Server-side tool loop can pause after many search rounds; resume once.
            if response.stop_reason == "pause_turn":
                response = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=[
                        {"role": "user", "content": user_content},
                        {"role": "assistant", "content": response.content},
                    ],
                )

            cost = _estimate_cost(response, model)
            total_cost += cost
            raw_text = _extract_text(response)
            last_raw = raw_text
            _log_call(log_path, attempt, user_content, raw_text, cost)

            entries, no_trade_day, notes = _parse_and_validate(raw_text, watchlist_size, alpaca)
            return SelectionResult(
                watchlist=entries,
                no_trade_day=no_trade_day or not entries,
                notes=notes,
                raw_response=raw_text,
                cost_usd=total_cost,
                screen_candidates=candidates,
            )
        except (SelectionError, anthropic.APIError) as exc:
            last_error = exc
            logger.warning("Ticker selection attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2)

    logger.error("Ticker selection failed twice; treating as no-trade day. Last error: %s", last_error)
    return SelectionResult(
        watchlist=[],
        no_trade_day=True,
        notes=f"Claude call failed twice: {last_error}",
        raw_response=last_raw,
        cost_usd=total_cost,
        screen_candidates=candidates,
    )


def _log_call(log_path: Path, attempt: int, request_text: str, response_text: str, cost: float) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"\n--- ticker selection attempt {attempt + 1} (cost=${cost:.4f}) ---\n")
        fh.write(f"REQUEST:\n{request_text}\n")
        fh.write(f"RESPONSE:\n{response_text}\n")
