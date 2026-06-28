"""
Localhost-only FastAPI server exposing the same controls as the relay RPC.

Binds strictly to 127.0.0.1 so only the wizard (running on the same machine)
can reach it. Imports and calls the same handler functions used by the relay
client, so there is a single source of truth for business logic.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from bot.control.connection import DbConn, get_db_connection
from bot.control.handlers import (
    handle_get_daily_pl,
    handle_get_lists,
    handle_get_order_detail,
    handle_get_settings,
    handle_get_state,
    handle_get_ticker_detail,
    handle_get_trade_history,
    handle_trigger_scan,
    handle_update_lists,
    handle_update_settings,
)

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="QuickStockBot Localhost API",
    description="Control interface for the setup wizard — localhost only.",
    version="1.0.0",
)


def _get_db() -> DbConn:
    """Create a fresh PostgreSQL connection for each request."""
    return get_db_connection()


# ─── Routes ───────────────────────────────────────────────────────────────────


@app.get("/state")
def api_get_state(db: DbConn = Depends(_get_db)) -> JSONResponse:
    return JSONResponse(handle_get_state(db, {}))


@app.get("/tickers")
def api_get_active_tickers(db: DbConn = Depends(_get_db)) -> JSONResponse:
    from bot.control import db as dbmod

    return JSONResponse({"tickers": dbmod.get_all_tickers(db)})


@app.get("/tickers/{symbol}")
def api_get_ticker_detail(
    symbol: str, db: DbConn = Depends(_get_db)
) -> JSONResponse:
    try:
        return JSONResponse(handle_get_ticker_detail(db, {"symbol": symbol}))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/settings")
def api_get_settings(db: DbConn = Depends(_get_db)) -> JSONResponse:
    return JSONResponse(handle_get_settings(db, {}))


class SettingsPatch(BaseModel):
    patch: dict


@app.patch("/settings")
def api_update_settings(
    body: SettingsPatch, db: DbConn = Depends(_get_db)
) -> JSONResponse:
    try:
        return JSONResponse(handle_update_settings(db, {"patch": body.patch}))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/lists")
def api_get_lists(db: DbConn = Depends(_get_db)) -> JSONResponse:
    return JSONResponse(handle_get_lists(db, {}))


class ListsBody(BaseModel):
    watchlist: list[str] | None = None
    blacklist: list[str] | None = None


@app.put("/lists")
def api_update_lists(
    body: ListsBody, db: DbConn = Depends(_get_db)
) -> JSONResponse:
    params: dict = {}
    if body.watchlist is not None:
        params["watchlist"] = body.watchlist
    if body.blacklist is not None:
        params["blacklist"] = body.blacklist
    return JSONResponse(handle_update_lists(db, params))


@app.get("/trades")
def api_get_trade_history(
    limit: int = 100,
    offset: int = 0,
    db: DbConn = Depends(_get_db),
) -> JSONResponse:
    return JSONResponse(
        handle_get_trade_history(db, {"limit": limit, "offset": offset})
    )


@app.get("/orders/{order_id}")
def api_get_order_detail(
    order_id: str, db: DbConn = Depends(_get_db)
) -> JSONResponse:
    try:
        return JSONResponse(handle_get_order_detail(db, {"order_id": order_id}))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/daily-pl")
def api_get_daily_pl(
    start: str,
    end: str,
    db: DbConn = Depends(_get_db),
) -> JSONResponse:
    try:
        return JSONResponse(handle_get_daily_pl(db, {"start": start, "end": end}))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/scan/trigger")
def api_trigger_scan(db: DbConn = Depends(_get_db)) -> JSONResponse:
    return JSONResponse(handle_trigger_scan(db, {}))


@app.get("/logs")
def api_get_logs(
    limit: int = 100, db: DbConn = Depends(_get_db)
) -> JSONResponse:
    rows = db.execute(
        "SELECT id, level, message, context, occurred_at FROM log_events"
        " ORDER BY occurred_at DESC LIMIT %s",
        (limit,),
    ).fetchall()
    logs = [
        {
            "id": r["id"],
            "level": r["level"],
            "message": r["message"],
            "context": r["context"],
            "occurred_at": r["occurred_at"],
        }
        for r in rows
    ]
    return JSONResponse({"logs": logs})


# ─── Entrypoint ───────────────────────────────────────────────────────────────


def serve(port: int = 8765) -> None:
    """Start the localhost API server. Binds to 127.0.0.1 only."""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port)
