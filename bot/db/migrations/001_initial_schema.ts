export const migration001 = {
  version: 1,
  name: '001_initial_schema',
  sql: `
    CREATE TABLE settings (
      key        TEXT    PRIMARY KEY,
      value      TEXT    NOT NULL,
      updated_at INTEGER NOT NULL
    );

    CREATE TABLE active_tickers (
      symbol     TEXT    PRIMARY KEY,
      price      REAL    NOT NULL,
      volume     REAL    NOT NULL,
      rsi        REAL,
      macd       REAL,
      signal     REAL,
      ema_short  REAL,
      ema_long   REAL,
      state      TEXT    NOT NULL,
      updated_at INTEGER NOT NULL
    );

    CREATE TABLE orders (
      id              TEXT    PRIMARY KEY,
      symbol          TEXT    NOT NULL,
      side            TEXT    NOT NULL,
      order_type      TEXT    NOT NULL,
      quantity        REAL    NOT NULL,
      limit_price     REAL,
      stop_price      REAL,
      filled_price    REAL,
      filled_quantity REAL,
      status          TEXT    NOT NULL,
      broker_order_id TEXT,
      created_at      INTEGER NOT NULL,
      updated_at      INTEGER NOT NULL
    );

    CREATE TABLE order_status_events (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      order_id        TEXT    NOT NULL REFERENCES orders(id),
      status          TEXT    NOT NULL,
      filled_price    REAL,
      filled_quantity REAL,
      message         TEXT,
      occurred_at     INTEGER NOT NULL
    );

    CREATE TABLE trades (
      id             TEXT    PRIMARY KEY,
      symbol         TEXT    NOT NULL,
      entry_order_id TEXT    NOT NULL REFERENCES orders(id),
      exit_order_id  TEXT    REFERENCES orders(id),
      entry_price    REAL    NOT NULL,
      exit_price     REAL,
      quantity       REAL    NOT NULL,
      gross_pnl      REAL,
      net_pnl        REAL,
      fees           REAL    NOT NULL DEFAULT 0,
      label          TEXT,
      status         TEXT    NOT NULL,
      opened_at      INTEGER NOT NULL,
      closed_at      INTEGER
    );

    CREATE TABLE log_events (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      level       TEXT    NOT NULL,
      message     TEXT    NOT NULL,
      context     TEXT,
      occurred_at INTEGER NOT NULL
    );

    CREATE TABLE lists (
      id        INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol    TEXT    NOT NULL,
      list_type TEXT    NOT NULL,
      reason    TEXT,
      active    INTEGER NOT NULL DEFAULT 1,
      added_at  INTEGER NOT NULL,
      UNIQUE(symbol, list_type)
    );

    CREATE TABLE ml_samples (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol        TEXT    NOT NULL,
      features      TEXT    NOT NULL,
      label         INTEGER,
      model_version TEXT,
      trade_id      TEXT    REFERENCES trades(id),
      sampled_at    INTEGER NOT NULL
    );

    CREATE INDEX idx_order_status_events_order_id   ON order_status_events(order_id);
    CREATE INDEX idx_order_status_events_occurred   ON order_status_events(occurred_at);
    CREATE INDEX idx_trades_entry_order_id          ON trades(entry_order_id);
    CREATE INDEX idx_trades_exit_order_id           ON trades(exit_order_id);
    CREATE INDEX idx_log_events_occurred            ON log_events(occurred_at);
    CREATE INDEX idx_lists_symbol                   ON lists(symbol);
    CREATE INDEX idx_ml_samples_trade_id            ON ml_samples(trade_id);
  `,
};
