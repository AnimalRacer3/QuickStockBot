# QuickStockBot

A stock trading bot that buys stocks meeting specific criteria, with a dashboard UI for monitoring and control.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   ┌───────┐   WebSocket    ┌─────────┐   HTTP/WS  ┌──────┐  │
│   │  Bot  ├───────────────►  Relay  ◄─────────────┤  Web │  │
│   └───────┘                └─────────┘            └──────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Packages

| Package | Lang | Purpose |
|---------|------|---------|
| `/bot` | Python | Trading engine — connects to broker (Alpaca), scans tickers, executes orders, streams events to Relay |
| `/web` | Next.js / TypeScript | Dashboard — live ticker state, order book, trade history, settings editor |
| `/relay` | Node.js / TypeScript | WebSocket bridge — authenticates bot connections, fans out events to web clients, proxies RPC calls |
| `/installer` | Shell / Node | One-click setup — downloads binaries, writes config, registers as a system service |
| `/shared` | JSON Schema / TS / Python | **Frozen contracts** — data models, relay wire protocol, env-var conventions; every other package builds against these |

### Data Flow

1. **Bot → Relay** (WebSocket): Bot authenticates with `license_key + bot_id + connection_password_proof`, then streams `state_update` and `log` frames.
2. **Web → Relay** (HTTP / WebSocket): Dashboard subscribes to live state; issues `rpc_request` frames that the Relay forwards to the Bot.
3. **Bot → Relay** (RPC response): Bot handles the request and returns an `rpc_response` frame; Relay proxies it back to the requesting Web client.

### Frozen Contracts

All wire formats and data shapes live in `/shared` and are considered frozen once merged.  
Any breaking change requires a new schema version and explicit review.

See [`shared/protocol/relay-protocol.json`](shared/protocol/relay-protocol.json) for the full Relay wire protocol  
and [`shared/schemas/`](shared/schemas/) for JSON Schemas of every data model.

## Quick Start

```bash
# Bot (Python)
cd bot && uv sync --group dev && uv run pytest

# Web (Next.js)
cd web && npm install && npm test

# Relay (Node)
cd relay && npm install && npm test

# Shared contract validation
cd shared && npm install && npm test
```

## CI

GitHub Actions runs lint + tests for every package on every PR.  
See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).
