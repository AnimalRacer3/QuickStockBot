#!/usr/bin/env python
"""Manual integration verification script.

Usage (from repo root, with paper keys in .env):
    pip install python-dotenv
    python scripts/manual_verify_alpaca.py

This hits the real Alpaca paper API — do NOT run with live keys.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()

if os.environ.get("ALPACA_ENV", "paper").lower() == "live":
    raise SystemExit("ERROR: This script must only be run with ALPACA_ENV=paper.")

from bot.alpaca.client import AlpacaClient
from bot.alpaca.config import AlpacaConfig
from shared.models import OrderSide, OrderType

cfg = AlpacaConfig.from_env()
client = AlpacaClient(cfg)

print("=== Account ===")
acct = client.get_account()
print(f"  equity=${acct.equity}  buying_power=${acct.buying_power}  PDT={acct.pattern_day_trader}")

print("\n=== Latest quote: AAPL ===")
quote = client.get_latest_quote("AAPL")
print(f"  bid={quote.bid_price}  ask={quote.ask_price}  mid={quote.mid_price}")

print("\n=== Historical bars: AAPL (last 5 min) ===")
now = datetime.now(timezone.utc)
bars = client.get_bars("AAPL", now - timedelta(minutes=10), now, limit=5)
for b in bars:
    print(f"  {b.timestamp.isoformat()}  O={b.open} H={b.high} L={b.low} C={b.close} V={b.volume}")

print("\n=== Submitting paper market order: 1 share of AAPL ===")
order = client.submit_order("AAPL", Decimal("1"), OrderSide.BUY, OrderType.MARKET)
print(f"  order_id={order.id}  status={order.status}")

print("\n=== Polling order to terminal state ===")
final = client.poll_order(order.id, timeout_seconds=30)
print(f"  final_status={final.status}  filled_qty={final.filled_qty}  avg_price={final.filled_avg_price}")

print("\n=== Positions ===")
for pos in client.list_positions():
    print(f"  {pos.symbol}  qty={pos.qty}  entry={pos.avg_entry_price}  current={pos.current_price}")

print("\nDone — all operations completed on paper account. Nothing live-traded.")
