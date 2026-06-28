"""
Database connection adapter supporting both psycopg2 (production, via DATABASE_URL)
and sqlite3 (tests, via in-memory DB).

All application SQL must use %s placeholders and PostgreSQL-compatible ON CONFLICT
syntax.  DbConn transparently translates %s → ? when wrapping a SQLite connection.
"""

from __future__ import annotations

import os
from typing import Any, Iterator

# ─── Row wrapper ──────────────────────────────────────────────────────────────


class _Row:
    """
    Uniform row type returned by DbCursor.  Supports:
      - row["colname"]  — key access
      - row[0]          — positional index access
      - dict(row)       — conversion to plain dict (via mapping protocol)
      - for v in row:   — iteration over values (enables "for k, v in rows:" unpacking)
      - bool(row)       — True for non-empty rows
    """

    __slots__ = ("_data", "_keys")

    def __init__(self, data: dict) -> None:
        self._data: dict[str, Any] = data
        self._keys: list[str] = list(data.keys())

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._data[self._keys[key]]
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def keys(self) -> Any:
        return self._data.keys()

    def values(self) -> Any:
        return self._data.values()

    def items(self) -> Any:
        return self._data.items()

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data.values())

    def __bool__(self) -> bool:
        return bool(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"_Row({self._data!r})"


def _to_row(raw: Any) -> _Row | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return _Row(dict(raw))
    return _Row(dict(raw))


# ─── Cursor wrapper ────────────────────────────────────────────────────────────


class DbCursor:
    """Thin wrapper around a raw database cursor; normalizes row access to _Row."""

    def __init__(self, cur: Any) -> None:
        self._cur = cur

    def fetchone(self) -> _Row | None:
        return _to_row(self._cur.fetchone())

    def fetchall(self) -> list[_Row]:
        return [
            r for r in (_to_row(raw) for raw in self._cur.fetchall()) if r is not None
        ]

    def __iter__(self) -> Iterator[_Row]:
        for raw in self._cur:
            row = _to_row(raw)
            if row is not None:
                yield row


# ─── Connection wrapper ────────────────────────────────────────────────────────


class DbConn:
    """
    Database connection adapter.

    For psycopg2 (production):  passes %s placeholders through unchanged, returns
                                 RealDictRow objects wrapped in _Row.
    For sqlite3 (tests):         translates %s → ? and wraps sqlite3.Row in _Row.

    All application SQL must be written with %s placeholders and PostgreSQL/SQLite-
    compatible ON CONFLICT syntax (SQLite 3.24+ supports this).
    """

    def __init__(self, conn: Any, pg: bool = False) -> None:
        self._conn = conn
        self._pg = pg

    # ── SQL translation ─────────────────────────────────────────────────────

    def _sql(self, sql: str) -> str:
        if not self._pg:
            return sql.replace("%s", "?")
        return sql

    # ── Core operations ─────────────────────────────────────────────────────

    def execute(self, sql: str, params: tuple | list = ()) -> DbCursor:
        sql = self._sql(sql)
        if self._pg:
            cur = self._conn.cursor()
            cur.execute(sql, params)
        else:
            cur = self._conn.execute(sql, params)
        return DbCursor(cur)

    def executemany(self, sql: str, params_seq: list) -> None:
        sql = self._sql(sql)
        if self._pg:
            cur = self._conn.cursor()
            cur.executemany(sql, params_seq)
        else:
            self._conn.executemany(sql, params_seq)

    def executescript(self, sql: str) -> None:
        """Run a multi-statement SQL script."""
        if self._pg:
            cur = self._conn.cursor()
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
            self._conn.commit()
        else:
            self._conn.executescript(sql)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @property
    def pg(self) -> bool:
        return self._pg


# ─── Factory ──────────────────────────────────────────────────────────────────


def get_db_connection() -> DbConn:
    """
    Create a PostgreSQL connection from the DATABASE_URL environment variable.

    Raises RuntimeError if DATABASE_URL is not set.
    Raises ImportError if psycopg2 is not installed.
    """
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError as exc:
        raise ImportError(
            "psycopg2 is required for PostgreSQL support. "
            "Install it with: pip install psycopg2-binary"
        ) from exc

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return DbConn(conn, pg=True)
