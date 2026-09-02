"""Stateful paper-trading position manager for the Market Regime Risk Engine.

This script downloads fresh hourly ETC-USD candles, evaluates the newest fully
completed candle, opens at most one simulated position, and persists that
position across runs. Open positions are checked against every completed candle
that arrived since the previous run, so skipped hours are still processed.

No brokerage connection is included. The script cannot place real orders.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
import os


# ======================
# CONFIGURATION
# ======================

ENGINE_VERSION = "paper_trader_v3_position_manager"
TICKER = os.getenv("PAPER_MARKET", "ETC-USD")
INTERVAL = "1h"
PERIOD = "60d"

ATR_LEN = 14
FAST_MA = 20
SLOW_MA = 50
RANGE_LOOKBACK = 20
BUFFER = 0.001

STOP_ATR = 1.0
TP_ATR = 2.0
MIN_EDGE_SCORE = 75
MIN_ATR_PCT = 0.001
MAX_ATR_PCT = 0.01

START_EQUITY = 10_000.0
RISK_PCT = 0.01
CONSERVATIVE_IF_BOTH_HIT = True

DEBUG = False
LOG_WAIT_DECISIONS = True

ENGINE_RUN_LOG_FIELDS = [
    "started_at_utc",
    "finished_at_utc",
    "market",
    "interval",
    "engine_version",
    "status",
    "rows_before",
    "rows_after",
    "new_signal_rows",
    "candle_before",
    "candle_after",
    "error",
]


# ======================
# PATHS
# ======================

def project_root() -> Path:
    """Return the directory containing this script."""
    return Path(__file__).resolve().parent

def analysis_dir() -> Path:
    """Create and return the paper-trading output directory."""
    path = project_root() / "analysis"
    path.mkdir(parents=True, exist_ok=True)
    return path

def market_slug() -> str:
    return TICKER.replace("-", "_").lower()


def signal_log_path() -> Path:
    # Preserve existing ETC files so the current dashboard keeps working.
    if TICKER == "ETC-USD":
        return analysis_dir() / "paper_trade_signal_log.csv"

    return analysis_dir() / f"paper_trade_signal_log_{market_slug()}.csv"


def position_state_path() -> Path:
    if TICKER == "ETC-USD":
        return analysis_dir() / "paper_trade_position_state.csv"

    return analysis_dir() / f"paper_trade_position_state_{market_slug()}.csv"


def trade_history_path() -> Path:
    if TICKER == "ETC-USD":
        return analysis_dir() / "paper_trade_trades.csv"

    return analysis_dir() / f"paper_trade_trades_{market_slug()}.csv"

def engine_run_log_path() -> Path:
    return analysis_dir() / "paper_engine_run_log.csv"


def signal_log_snapshot() -> tuple[int, str]:
    """Return the current row count and newest candle in this market's signal log."""
    path = signal_log_path()

    if not path.exists() or path.stat().st_size == 0:
        return 0, ""

    try:
        signal_log = pd.read_csv(path)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
        return 0, ""

    candle_after = ""
    if "candle_time_utc" in signal_log.columns and not signal_log.empty:
        candle_times = pd.to_datetime(
            signal_log["candle_time_utc"],
            errors="coerce",
            utc=True,
        ).dropna()
        if not candle_times.empty:
            candle_after = candle_times.max().isoformat()

    return len(signal_log), candle_after


def append_engine_run_log(record: dict[str, Any]) -> None:
    """Append one engine execution record to the shared audit log."""
    path = engine_run_log_path()
    write_header = not path.exists() or path.stat().st_size == 0

    with path.open("a", newline="", encoding="utf-8") as audit_file:
        writer = csv.DictWriter(audit_file, fieldnames=ENGINE_RUN_LOG_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(record)

# ======================
# DATA
# ======================


def download_recent_data() -> pd.DataFrame:
    """Download fresh intraday data from Yahoo Finance."""
    df = yf.download(
        tickers=TICKER,
        interval=INTERVAL,
        period=PERIOD,
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if df.empty:
        raise RuntimeError(f"No data returned for {TICKER}.")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return clean_ohlc(df.reset_index())


def clean_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize timestamps and required OHLC columns."""
    out = df.copy()
    timestamp_col = next(
        (column for column in ("Datetime", "Date", "index") if column in out.columns),
        None,
    )
    if timestamp_col is None:
        raise ValueError(f"No timestamp column found. Columns: {list(out.columns)}")

    out = out.rename(columns={timestamp_col: "timestamp"})
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce", utc=True)

    required = ["Open", "High", "Low", "Close"]
    for column in required:
        if column not in out.columns and column.lower() in out.columns:
            out[column] = out[column.lower()]
        if column not in out.columns:
            raise ValueError(f"Missing column '{column}'. Columns: {list(out.columns)}")
        out[column] = pd.to_numeric(out[column], errors="coerce")

    return (
        out.dropna(subset=["timestamp", *required])
        .sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"], keep="last")
        .reset_index(drop=True)
    )


def keep_completed_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Remove the currently forming hourly candle."""
    now_utc = pd.Timestamp.now(tz="UTC")
    completed = df[df["timestamp"] + pd.Timedelta(hours=1) <= now_utc].copy()
    if completed.empty:
        raise RuntimeError("No fully completed hourly candles are available yet.")
    return completed.reset_index(drop=True)


# ======================
# FEATURES AND SIGNALS
# ======================


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate the indicators used by the historical engine."""
    out = df.copy()
    out["ma20"] = out["Close"].rolling(FAST_MA).mean()
    out["ma50"] = out["Close"].rolling(SLOW_MA).mean()

    out["trend_dir"] = 0
    out.loc[out["ma20"] > out["ma50"], "trend_dir"] = 1
    out.loc[out["ma20"] < out["ma50"], "trend_dir"] = -1

    previous_close = out["Close"].shift(1)
    true_range = pd.concat(
        [
            out["High"] - out["Low"],
            (out["High"] - previous_close).abs(),
            (out["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    out["atr"] = true_range.rolling(ATR_LEN).mean()
    out["atr_pct"] = out["atr"] / out["Close"]

    delta = out["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    average_gain = gain.rolling(14).mean()
    average_loss = loss.rolling(14).mean()
    relative_strength = average_gain / average_loss.replace(0, np.nan)
    out["rsi"] = 100 - (100 / (1 + relative_strength))

    out["range_high"] = out["High"].rolling(RANGE_LOOKBACK).max().shift(1)
    out["range_low"] = out["Low"].rolling(RANGE_LOOKBACK).min().shift(1)
    out["ma_gap_pct"] = (out["ma20"] - out["ma50"]).abs() / out["Close"]
    out["atr_pct_mean50"] = out["atr_pct"].rolling(50).mean()

    out["is_range"] = (
        (out["atr_pct"] < out["atr_pct_mean50"])
        & (out["ma_gap_pct"] < 0.003)
        & out["rsi"].between(45, 55)
    )
    out["regime"] = "TREND"
    out.loc[out["is_range"], "regime"] = "RANGE"
    return out


def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Generate fake-breakout and range decisions."""
    out = df.copy()

    fake_break_long = (
        (out["regime"] == "RANGE")
        & (out["Low"] < out["range_low"])
        & (out["Close"] > out["range_low"])
    )
    fake_break_short = (
        (out["regime"] == "RANGE")
        & (out["High"] > out["range_high"])
        & (out["Close"] < out["range_high"])
    )
    range_long = (
        (out["regime"] == "RANGE")
        & (out["Close"] <= out["range_low"] * (1 + BUFFER))
        & (out["rsi"] < 50)
    )
    range_short = (
        (out["regime"] == "RANGE")
        & (out["Close"] >= out["range_high"] * (1 - BUFFER))
        & (out["rsi"] > 50)
    )

    out["decision"] = "WAIT"
    out.loc[fake_break_long & (out["rsi"] < 50), "decision"] = "GO_FAKE_LONG"
    out.loc[fake_break_short & (out["rsi"] > 50), "decision"] = "GO_FAKE_SHORT"
    out.loc[(out["decision"] == "WAIT") & range_long, "decision"] = "GO_RANGE_LONG"
    out.loc[(out["decision"] == "WAIT") & range_short, "decision"] = "GO_RANGE_SHORT"

    out["signal"] = 0
    out.loc[out["decision"].isin(["GO_FAKE_LONG", "GO_RANGE_LONG"]), "signal"] = 1
    out.loc[out["decision"].isin(["GO_FAKE_SHORT", "GO_RANGE_SHORT"]), "signal"] = -1
    return out


# ======================
# DECISION LOGIC
# ======================


def calculate_edge_score(row: pd.Series) -> int:
    """Calculate the discrete edge score used by the backtest."""
    signal = int(row["signal"])
    close = float(row["Close"])
    entry_range_pct = float(row["High"] - row["Low"]) / close if close else 0.0
    ma_distance_pct = abs(close - float(row["ma20"])) / close if close else 0.0

    edge_score = 30 if signal == 1 else 10

    if entry_range_pct <= 0.005:
        edge_score += 30
    elif entry_range_pct <= 0.010:
        edge_score += 20
    else:
        edge_score += 5

    if 0.002 <= ma_distance_pct <= 0.010:
        edge_score += 25
    elif ma_distance_pct < 0.002:
        edge_score += 15
    else:
        edge_score += 10

    if int(row["trend_dir"]) != 0:
        edge_score += 15
    return edge_score


def evaluate_candle(row: pd.Series) -> dict[str, Any]:
    """Evaluate one completed candle as a potential new entry."""
    required = ["atr", "atr_pct", "rsi", "ma20", "ma50", "range_high", "range_low"]
    if row[required].isna().any():
        raise RuntimeError("Not enough completed data to calculate all indicators.")

    raw_decision = str(row["decision"])
    signal = int(row["signal"])
    rsi = float(row["rsi"])
    atr = float(row["atr"])
    atr_pct = float(row["atr_pct"])
    close = float(row["Close"])

    allowed_signal = raw_decision in {"GO_FAKE_LONG", "GO_FAKE_SHORT"}
    allowed_rsi = 30 <= rsi <= 60
    allowed_atr = MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT
    edge_score = calculate_edge_score(row) if signal != 0 else 0

    qualifies = (
        signal != 0
        and allowed_signal
        and allowed_rsi
        and allowed_atr
        and edge_score >= MIN_EDGE_SCORE
    )

    reasons: list[str] = []
    if signal == 0:
        reasons.append("no signal")
    elif not allowed_signal:
        reasons.append("signal type not allowed")
    if not allowed_rsi:
        reasons.append("RSI outside 30-60")
    if not allowed_atr:
        reasons.append("ATR percentage outside limits")
    if signal != 0 and edge_score < MIN_EDGE_SCORE:
        reasons.append(f"edge score below {MIN_EDGE_SCORE}")

    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candle_time_utc": row["timestamp"].isoformat(),
        "engine_version": ENGINE_VERSION,
        "market": TICKER,
        "interval": INTERVAL,
        "close": close,
        "regime": str(row["regime"]),
        "raw_decision": raw_decision,
        "decision": raw_decision if qualifies else "WAIT",
        "signal": signal,
        "direction": "LONG" if qualifies and signal == 1 else "SHORT" if qualifies else "NONE",
        "edge_score": edge_score,
        "rsi": rsi,
        "atr": atr,
        "atr_pct": atr_pct,
        "status": "QUALIFYING_SIGNAL" if qualifies else "NO_TRADE",
        "reason": "All entry filters passed." if qualifies else ", ".join(reasons),
    }


# ======================
# PERSISTENT STATE
# ======================


def load_position_state() -> dict[str, Any] | None:
    """Load the open position for the configured market, if one exists."""
    path = position_state_path()
    if not path.exists():
        return None

    states = pd.read_csv(path)
    if states.empty or "market" not in states.columns or "status" not in states.columns:
        return None

    match = states[(states["market"].astype(str) == TICKER) & (states["status"] == "OPEN")]
    if match.empty:
        return None
    return match.iloc[-1].to_dict()


def save_position_state(position: dict[str, Any] | None) -> None:
    """Persist the current position state for this single-market prototype."""
    path = position_state_path()
    if position is None:
        if path.exists():
            path.unlink()
        return
    pd.DataFrame([position]).to_csv(path, index=False)


def append_trade_history(trade: dict[str, Any]) -> None:
    """Append one closed paper trade to the permanent trade history."""
    path = trade_history_path()
    row = pd.DataFrame([trade])
    if path.exists():
        row.to_csv(path, mode="a", header=False, index=False)
    else:
        row.to_csv(path, index=False)


def append_signal_log(record: dict[str, Any]) -> bool:
    """Append one unique market/candle observation to the signal log."""
    path = signal_log_path()
    row = pd.DataFrame([record])

    if path.exists():
        existing = pd.read_csv(path)
        if not existing.empty and {"market", "candle_time_utc"}.issubset(existing.columns):
            duplicate = (
                (existing["market"].astype(str) == str(record["market"]))
                & (existing["candle_time_utc"].astype(str) == str(record["candle_time_utc"]))
            ).any()
            if duplicate:
                return False
        row.to_csv(path, mode="a", header=False, index=False)
    else:
        row.to_csv(path, index=False)
    return True


# ======================
# POSITION MANAGEMENT
# ======================


def open_position(decision: dict[str, Any]) -> dict[str, Any]:
    """Create a new simulated position from a qualifying signal."""
    entry = float(decision["close"])
    atr = float(decision["atr"])
    direction = str(decision["direction"])

    if direction == "LONG":
        stop = entry - STOP_ATR * atr
        target = entry + TP_ATR * atr
    else:
        stop = entry + STOP_ATR * atr
        target = entry - TP_ATR * atr

    risk_per_unit = abs(entry - stop)
    risk_dollars = START_EQUITY * RISK_PCT
    simulated_units = risk_dollars / risk_per_unit if risk_per_unit > 0 else 0.0

    return {
        "engine_version": ENGINE_VERSION,
        "market": TICKER,
        "status": "OPEN",
        "direction": direction,
        "entry_signal": decision["decision"],
        "entry_time_utc": decision["candle_time_utc"],
        "opened_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entry_price": entry,
        "stop_price": stop,
        "target_price": target,
        "entry_atr": atr,
        "edge_score": int(decision["edge_score"]),
        "entry_rsi": float(decision["rsi"]),
        "entry_regime": decision["regime"],
        "risk_dollars": risk_dollars,
        "simulated_units": simulated_units,
        "bars_held": 0,
        "last_checked_candle_utc": decision["candle_time_utc"],
        "last_close": entry,
        "current_r": 0.0,
    }


def current_r_multiple(position: dict[str, Any], current_price: float) -> float:
    """Return unrealized R using the original stop distance."""
    entry = float(position["entry_price"])
    stop = float(position["stop_price"])
    risk_per_unit = abs(entry - stop)
    if risk_per_unit == 0:
        return 0.0
    if position["direction"] == "LONG":
        return (current_price - entry) / risk_per_unit
    return (entry - current_price) / risk_per_unit


def manage_open_position(
    position: dict[str, Any],
    completed_df: pd.DataFrame,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, int]:
    """Process all new candles since the position was last checked."""
    last_checked = pd.to_datetime(position["last_checked_candle_utc"], utc=True)
    new_candles = completed_df[completed_df["timestamp"] > last_checked].copy()

    if new_candles.empty:
        return position, None, 0

    processed = 0
    for _, candle in new_candles.iterrows():
        processed += 1
        position["bars_held"] = int(float(position.get("bars_held", 0))) + 1

        high = float(candle["High"])
        low = float(candle["Low"])
        close = float(candle["Close"])
        direction = str(position["direction"])
        stop = float(position["stop_price"])
        target = float(position["target_price"])

        if direction == "LONG":
            stop_hit = low <= stop
            target_hit = high >= target
        else:
            stop_hit = high >= stop
            target_hit = low <= target

        exit_reason: str | None = None
        exit_price: float | None = None

        if stop_hit and target_hit:
            if CONSERVATIVE_IF_BOTH_HIT:
                exit_reason, exit_price = "STOP_LOSS_BOTH_HIT", stop
            else:
                exit_reason, exit_price = "TAKE_PROFIT_BOTH_HIT", target
        elif stop_hit:
            exit_reason, exit_price = "STOP_LOSS", stop
        elif target_hit:
            exit_reason, exit_price = "TAKE_PROFIT", target

        position["last_checked_candle_utc"] = candle["timestamp"].isoformat()
        position["last_close"] = close
        position["current_r"] = current_r_multiple(position, close)

        if exit_reason is not None and exit_price is not None:
            r_multiple = -1.0 if "STOP_LOSS" in exit_reason else TP_ATR / STOP_ATR
            pnl_dollars = float(position["risk_dollars"]) * r_multiple
            trade = {
                **position,
                "status": "CLOSED",
                "exit_time_utc": candle["timestamp"].isoformat(),
                "closed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "r_multiple": r_multiple,
                "pnl_dollars": pnl_dollars,
            }
            append_trade_history(trade)
            return None, trade, processed

    return position, None, processed

def last_logged_candle_time() -> pd.Timestamp | None:
    """Return the newest candle already stored in the signal log."""
    path = signal_log_path()

    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        log = pd.read_csv(path)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
        return None

    if "candle_time_utc" not in log.columns or log.empty:
        return None

    times = pd.to_datetime(
        log["candle_time_utc"],
        errors="coerce",
        utc=True,
    ).dropna()

    if times.empty:
        return None

    return times.max()
# ======================
# REPORTING
# ======================


def format_number(value: Any, digits: int = 4) -> str:
    if pd.isna(value):
        return "—"
    return f"{float(value):.{digits}f}"


def print_header() -> None:
    print("\n====================================")
    print("PAPER TRADER POSITION MANAGER")
    print("====================================")
    print(f"Engine:          {ENGINE_VERSION}")
    print(f"Market:          {TICKER}")
    print(f"Interval:        {INTERVAL}")
    print("Real orders:     disabled")


def print_opened(position: dict[str, Any], logged: bool) -> None:
    print("\nAction:          OPENED NEW PAPER POSITION")
    print(f"Direction:       {position['direction']}")
    print(f"Signal:          {position['entry_signal']}")
    print(f"Entry:           {format_number(position['entry_price'])}")
    print(f"Stop:            {format_number(position['stop_price'])}")
    print(f"Target:          {format_number(position['target_price'])}")
    print(f"Edge score:      {position['edge_score']}")
    print(f"Risk dollars:    {format_number(position['risk_dollars'], 2)}")
    print(f"Simulated units: {format_number(position['simulated_units'], 6)}")
    print(f"Signal log:      {'saved' if logged else 'duplicate candle — not saved again'}")


def print_position_update(position: dict[str, Any], processed: int) -> None:
    print("\nAction:          MANAGED OPEN POSITION")
    print(f"Direction:       {position['direction']}")
    print(f"Entry:           {format_number(position['entry_price'])}")
    print(f"Last close:      {format_number(position['last_close'])}")
    print(f"Stop:            {format_number(position['stop_price'])}")
    print(f"Target:          {format_number(position['target_price'])}")
    print(f"Current R:       {format_number(position['current_r'], 3)}")
    print(f"Bars held:       {int(float(position['bars_held']))}")
    print(f"New candles:     {processed}")
    print("Status:          OPEN")


def print_closed(trade: dict[str, Any], processed: int) -> None:
    print("\nAction:          CLOSED PAPER POSITION")
    print(f"Direction:       {trade['direction']}")
    print(f"Entry:           {format_number(trade['entry_price'])}")
    print(f"Exit:            {format_number(trade['exit_price'])}")
    print(f"Exit reason:     {trade['exit_reason']}")
    print(f"Result:          {format_number(trade['r_multiple'], 2)}R")
    print(f"P/L dollars:     {format_number(trade['pnl_dollars'], 2)}")
    print(f"Bars held:       {int(float(trade['bars_held']))}")
    print(f"New candles:     {processed}")
    print("Status:          CLOSED")


def print_no_trade(decision: dict[str, Any], logged: bool) -> None:
    print("\nAction:          NO NEW POSITION")
    print(f"Candle (UTC):    {decision['candle_time_utc']}")
    print(f"Close:           {format_number(decision['close'])}")
    print(f"Regime:          {decision['regime']}")
    print(f"Raw decision:    {decision['raw_decision']}")
    print(f"Final decision:  {decision['decision']}")
    print(f"Edge score:      {decision['edge_score']}")
    print(f"RSI:             {format_number(decision['rsi'], 2)}")
    print(f"Reason:          {decision['reason']}")
    print(f"Signal log:      {'saved' if logged else 'duplicate candle — not saved again'}")


def print_paths() -> None:
    print("\nFiles:")
    print(f"  Signal log:    {signal_log_path()}")
    print(f"  Position:      {position_state_path()}")
    print(f"  Trade history: {trade_history_path()}")
    print("====================================")


# ======================
# MAIN
# ======================


def run_engine_cycle() -> None:
    """Run one stateful paper-trading cycle."""
    try:
        df = download_recent_data()
        df = keep_completed_candles(df)
        df = add_features(df)
        df = add_signals(df)

        last_logged = last_logged_candle_time()

        if last_logged is None:
            candles_to_log = df.tail(1)
        else:
            candle_times = pd.to_datetime(df["timestamp"], utc=True)
            candles_to_log = df[candle_times > last_logged]

        logged_count = 0

        for _, candle in candles_to_log.iterrows():
            decision = evaluate_candle(candle)

            should_log = (
                    LOG_WAIT_DECISIONS
                    or decision["decision"] != "WAIT"
            )

            if should_log and append_signal_log(decision):
                logged_count += 1

        # Only the newest completed candle is eligible to open a NEW position.
        latest_decision = evaluate_candle(df.iloc[-1])
        logged = logged_count > 0

        print_header()
        print(f"Catch-up candles logged: {logged_count}")
        position = load_position_state()

        if position is not None:
            position, closed_trade, processed = manage_open_position(position, df)
            save_position_state(position)

            if closed_trade is not None:
                print_closed(closed_trade, processed)
            elif position is not None:
                print_position_update(position, processed)
        else:
            if latest_decision["status"] == "QUALIFYING_SIGNAL":
                position = open_position(latest_decision)
                save_position_state(position)
                print_opened(position, logged)
            else:
                print_no_trade(latest_decision, logged)

        print_paths()

        if DEBUG:
            print("\nLatest completed candle:")
            print(df.tail(1).to_string(index=False))

    except (RuntimeError, ValueError, KeyError, OSError, TypeError) as exc:
        print("\nPAPER TRADER ERROR")
        print(f"{type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc


def main() -> None:
    """Run one engine cycle and append its integrity audit record."""
    started_at_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows_before, candle_before = signal_log_snapshot()

    try:
        run_engine_cycle()
    except BaseException as exc:
        rows_after, candle_after = signal_log_snapshot()
        audit_error = exc.__cause__ if exc.__cause__ is not None else exc
        append_engine_run_log(
            {
                "started_at_utc": started_at_utc,
                "finished_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "market": TICKER,
                "interval": INTERVAL,
                "engine_version": ENGINE_VERSION,
                "status": "ERROR",
                "rows_before": rows_before,
                "rows_after": rows_after,
                "new_signal_rows": max(rows_after - rows_before, 0),
                "candle_before": candle_before,
                "candle_after": candle_after,
                "error": f"{type(audit_error).__name__}: {audit_error}",
            }
        )
        raise

    rows_after, candle_after = signal_log_snapshot()
    append_engine_run_log(
        {
            "started_at_utc": started_at_utc,
            "finished_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "market": TICKER,
            "interval": INTERVAL,
            "engine_version": ENGINE_VERSION,
            "status": "SUCCESS",
            "rows_before": rows_before,
            "rows_after": rows_after,
            "new_signal_rows": max(rows_after - rows_before, 0),
            "candle_before": candle_before,
            "candle_after": candle_after,
            "error": "",
        }
    )


if __name__ == "__main__":
    main()
