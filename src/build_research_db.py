"""Build a separate SQLite research copy from live paper-trading CSV logs.

The CSV files remain the source of truth. This importer only reads them and
inserts copies into ``analysis/market_research.db``.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterable


SRC_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = SRC_DIR / "analysis"
DATABASE_PATH = ANALYSIS_DIR / "market_research.db"

SIGNAL_FILES = (
    ANALYSIS_DIR / "paper_trade_signal_log.csv",
    ANALYSIS_DIR / "paper_trade_signal_log_btc_usd.csv",
)
TRADE_FILES = (
    ANALYSIS_DIR / "paper_trade_trades.csv",
    ANALYSIS_DIR / "paper_trade_trades_btc_usd.csv",
)
ENGINE_RUN_FILE = ANALYSIS_DIR / "paper_engine_run_log.csv"

SIGNAL_COLUMNS = (
    "checked_at_utc", "candle_time_utc", "engine_version", "market",
    "interval", "close", "regime", "raw_decision", "decision", "signal",
    "direction", "edge_score", "rsi", "atr", "atr_pct", "status", "reason",
)
ENGINE_RUN_COLUMNS = (
    "started_at_utc", "finished_at_utc", "market", "interval",
    "engine_version", "status", "rows_before", "rows_after",
    "new_signal_rows", "candle_before", "candle_after", "error",
)

INTEGER_COLUMNS = {
    "signal", "edge_score", "rows_before", "rows_after", "new_signal_rows",
    "bars_held",
}
REAL_COLUMNS = {
    "close", "rsi", "atr", "atr_pct", "entry_price", "stop_price",
    "target_price", "exit_price", "entry_atr", "risk_dollars",
    "simulated_units", "r_multiple", "pnl_dollars",
}


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a CSV without changing it; missing and empty files yield no rows."""
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    with path.open("r", newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            return [], []
        fieldnames = [name for name in reader.fieldnames if name]
        return fieldnames, [dict(row) for row in reader]


def sql_type(column: str) -> str:
    if column in INTEGER_COLUMNS:
        return "INTEGER"
    if column in REAL_COLUMNS:
        return "REAL"
    return "TEXT"


def converted(value: str | None, column: str) -> object:
    if value is None or value == "":
        return None
    try:
        if column in INTEGER_COLUMNS:
            return int(float(value))
        if column in REAL_COLUMNS:
            return float(value)
    except (TypeError, ValueError):
        return value
    return value


def quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS signal_checks (
            checked_at_utc TEXT,
            candle_time_utc TEXT NOT NULL,
            engine_version TEXT,
            market TEXT NOT NULL,
            interval TEXT,
            close REAL,
            regime TEXT,
            raw_decision TEXT,
            decision TEXT,
            signal INTEGER,
            direction TEXT,
            edge_score INTEGER,
            rsi REAL,
            atr REAL,
            atr_pct REAL,
            status TEXT,
            reason TEXT,
            UNIQUE (market, candle_time_utc)
        );

        CREATE TABLE IF NOT EXISTS engine_runs (
            started_at_utc TEXT NOT NULL,
            finished_at_utc TEXT,
            market TEXT NOT NULL,
            interval TEXT NOT NULL,
            engine_version TEXT,
            status TEXT,
            rows_before INTEGER,
            rows_after INTEGER,
            new_signal_rows INTEGER,
            candle_before TEXT,
            candle_after TEXT,
            error TEXT,
            UNIQUE (market, interval, started_at_utc)
        );

        CREATE TABLE IF NOT EXISTS trades (
            market TEXT,
            entry_time_utc TEXT,
            exit_time_utc TEXT,
            _source_file TEXT NOT NULL,
            _source_row INTEGER NOT NULL,
            _row_hash TEXT NOT NULL UNIQUE
        );

        CREATE INDEX IF NOT EXISTS idx_signal_checks_market ON signal_checks (market);
        CREATE INDEX IF NOT EXISTS idx_signal_checks_candle_time ON signal_checks (candle_time_utc);
        CREATE INDEX IF NOT EXISTS idx_signal_checks_status ON signal_checks (status);
        CREATE INDEX IF NOT EXISTS idx_signal_checks_regime ON signal_checks (regime);
        CREATE INDEX IF NOT EXISTS idx_engine_runs_market ON engine_runs (market);
        CREATE INDEX IF NOT EXISTS idx_engine_runs_status ON engine_runs (status);
        CREATE INDEX IF NOT EXISTS idx_engine_runs_started_at ON engine_runs (started_at_utc);
        CREATE INDEX IF NOT EXISTS idx_engine_runs_finished_at ON engine_runs (finished_at_utc);
        CREATE INDEX IF NOT EXISTS idx_trades_market ON trades (market);
        CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades (entry_time_utc);
        CREATE INDEX IF NOT EXISTS idx_trades_exit_time ON trades (exit_time_utc);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_natural_key
            ON trades (market, entry_time_utc)
            WHERE market IS NOT NULL AND entry_time_utc IS NOT NULL;
        """
    )


def insert_fixed_rows(
    connection: sqlite3.Connection,
    table: str,
    columns: tuple[str, ...],
    rows: Iterable[dict[str, str]],
) -> tuple[int, int]:
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(quoted(column) for column in columns)
    statement = f"INSERT OR IGNORE INTO {quoted(table)} ({column_sql}) VALUES ({placeholders})"
    inserted = 0
    seen = 0
    for row in rows:
        seen += 1
        before = connection.total_changes
        connection.execute(
            statement,
            tuple(converted(row.get(column), column) for column in columns),
        )
        inserted += connection.total_changes - before
    return seen, inserted


def ensure_trade_columns(connection: sqlite3.Connection, columns: Iterable[str]) -> list[str]:
    existing = {row[1] for row in connection.execute("PRAGMA table_info(trades)")}
    source_columns = [
        column for column in columns
        if column not in {"_source_file", "_source_row", "_row_hash"}
    ]
    for column in source_columns:
        if column not in existing:
            connection.execute(
                f"ALTER TABLE trades ADD COLUMN {quoted(column)} {sql_type(column)}"
            )
            existing.add(column)
    return source_columns


def insert_trade_rows(
    connection: sqlite3.Connection,
    path: Path,
    columns: list[str],
    rows: list[dict[str, str]],
) -> tuple[int, int]:
    source_columns = ensure_trade_columns(connection, columns)
    insert_columns = [*source_columns, "_source_file", "_source_row", "_row_hash"]
    column_sql = ", ".join(quoted(column) for column in insert_columns)
    placeholders = ", ".join("?" for _ in insert_columns)
    statement = f"INSERT OR IGNORE INTO trades ({column_sql}) VALUES ({placeholders})"
    inserted = 0
    for row_number, row in enumerate(rows, start=2):
        canonical = json.dumps(
            {column: row.get(column, "") for column in source_columns},
            sort_keys=True,
            separators=(",", ":"),
        )
        row_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        values = [converted(row.get(column), column) for column in source_columns]
        values.extend([path.name, row_number, row_hash])
        before = connection.total_changes
        connection.execute(statement, values)
        inserted += connection.total_changes - before
    return len(rows), inserted


def import_csv_copies(connection: sqlite3.Connection) -> None:
    for path in SIGNAL_FILES:
        _, rows = read_csv_rows(path)
        seen, inserted = insert_fixed_rows(connection, "signal_checks", SIGNAL_COLUMNS, rows)
        print(f"Imported {inserted}/{seen} new signal rows from {path.name}")

    for path in TRADE_FILES:
        columns, rows = read_csv_rows(path)
        seen, inserted = insert_trade_rows(connection, path, columns, rows)
        print(f"Imported {inserted}/{seen} new trade rows from {path.name}")

    _, engine_rows = read_csv_rows(ENGINE_RUN_FILE)
    seen, inserted = insert_fixed_rows(
        connection, "engine_runs", ENGINE_RUN_COLUMNS, engine_rows
    )
    print(f"Imported {inserted}/{seen} new engine-run rows from {ENGINE_RUN_FILE.name}")


def scalar(connection: sqlite3.Connection, statement: str) -> object:
    return connection.execute(statement).fetchone()[0]


def verify(connection: sqlite3.Connection) -> None:
    tables = [
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    print("\nVerification")
    print("Tables:", ", ".join(tables))
    for table in ("signal_checks", "trades", "engine_runs"):
        print(f"{table}: {scalar(connection, f'SELECT COUNT(*) FROM {table}')} rows")
        market_counts = connection.execute(
            f"""
            SELECT market, COUNT(*) FROM {quoted(table)}
            WHERE market IN ('ETC-USD', 'BTC-USD')
            GROUP BY market ORDER BY market
            """
        ).fetchall()
        counts = {market: count for market, count in market_counts}
        print(f"  ETC-USD={counts.get('ETC-USD', 0)}, BTC-USD={counts.get('BTC-USD', 0)}")

    earliest, latest = connection.execute(
        "SELECT MIN(candle_time_utc), MAX(candle_time_utc) FROM signal_checks"
    ).fetchone()
    print(f"Signal timestamps: earliest={earliest or 'N/A'}, latest={latest or 'N/A'}")

    duplicate_signals = scalar(connection, """
        SELECT COUNT(*) FROM (
            SELECT market, candle_time_utc FROM signal_checks
            GROUP BY market, candle_time_utc HAVING COUNT(*) > 1
        )
    """)
    duplicate_runs = scalar(connection, """
        SELECT COUNT(*) FROM (
            SELECT market, interval, started_at_utc FROM engine_runs
            GROUP BY market, interval, started_at_utc HAVING COUNT(*) > 1
        )
    """)
    duplicate_trades = scalar(connection, """
        SELECT COUNT(*) FROM (
            SELECT market, entry_time_utc FROM trades
            WHERE market IS NOT NULL AND entry_time_utc IS NOT NULL
            GROUP BY market, entry_time_utc HAVING COUNT(*) > 1
        )
    """)
    total_duplicates = duplicate_signals + duplicate_runs + duplicate_trades
    print(
        f"Duplicate-key count: {total_duplicates} "
        f"(signals={duplicate_signals}, trades={duplicate_trades}, "
        f"engine_runs={duplicate_runs})"
    )


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as connection:
        create_schema(connection)
        import_csv_copies(connection)
        connection.commit()
        verify(connection)
    print(f"\nResearch database: {DATABASE_PATH}")


if __name__ == "__main__":
    main()
