"""Paper-trading signal logger for the Market Regime Risk Engine.

This script evaluates the newest fully completed hourly candle for ETC-USD,
prints one decision, and records that decision to a CSV file. It does not
connect to a broker, submit orders, or use real money.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf


# ======================
# CONFIGURATION
# ======================

ENGINE_VERSION = "paper_trader_v2_signal_logger"
TICKER = "ETC-USD"
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

DEBUG = False
LOG_WAIT_DECISIONS = True


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


def signal_log_path() -> Path:
    """Return the CSV path used for live signal checks."""
    return analysis_dir() / "paper_trade_signal_log_BAD_BACKUP.csv"


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

    df = df.reset_index()
    return clean_ohlc(df)


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

    out = (
        out.dropna(subset=["timestamp", *required])
        .sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"], keep="last")
        .reset_index(drop=True)
    )
    return out


def keep_completed_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Remove any candle whose hourly interval has not fully closed yet."""
    now_utc = pd.Timestamp.now(tz="UTC")
    interval_length = pd.Timedelta(hours=1)
    completed = df[df["timestamp"] + interval_length <= now_utc].copy()

    if completed.empty:
        raise RuntimeError("No fully completed hourly candles are available yet.")

    return completed.reset_index(drop=True)


# ======================
# FEATURES AND SIGNALS
# ======================


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate the same core indicators used by the historical engine."""
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
# LIVE DECISION
# ======================


def calculate_edge_score(row: pd.Series) -> int:
    """Calculate the v41 discrete edge score for one completed candle."""
    signal = int(row["signal"])
    close = float(row["Close"])
    entry_range = float(row["High"] - row["Low"])
    ma_distance = abs(close - float(row["ma20"]))

    entry_range_pct = entry_range / close if close else 0.0
    ma_distance_pct = ma_distance / close if close else 0.0

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


def evaluate_latest_candle(df: pd.DataFrame) -> dict[str, Any]:
    """Evaluate only the newest fully completed candle."""
    row = df.iloc[-1]

    required_features = ["atr", "atr_pct", "rsi", "ma20", "ma50", "range_high", "range_low"]
    if row[required_features].isna().any():
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

    if qualifies:
        final_decision = raw_decision
        status = "QUALIFYING_SIGNAL"
        direction = "LONG" if signal == 1 else "SHORT"
        reference_entry = close
        if signal == 1:
            stop_price = reference_entry - STOP_ATR * atr
            target_price = reference_entry + TP_ATR * atr
        else:
            stop_price = reference_entry + STOP_ATR * atr
            target_price = reference_entry - TP_ATR * atr
        reason = "All signal, RSI, ATR, and edge-score filters passed."
    else:
        final_decision = "WAIT"
        status = "NO_TRADE"
        direction = "NONE"
        reference_entry = np.nan
        stop_price = np.nan
        target_price = np.nan

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
        reason = ", ".join(reasons) if reasons else "No qualifying setup."

    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candle_time_utc": row["timestamp"].isoformat(),
        "engine_version": ENGINE_VERSION,
        "market": TICKER,
        "interval": INTERVAL,
        "close": close,
        "regime": str(row["regime"]),
        "raw_decision": raw_decision,
        "decision": final_decision,
        "signal": signal,
        "direction": direction,
        "edge_score": edge_score,
        "rsi": rsi,
        "atr": atr,
        "atr_pct": atr_pct,
        "ma20": float(row["ma20"]),
        "ma50": float(row["ma50"]),
        "reference_entry": reference_entry,
        "stop_price": stop_price,
        "target_price": target_price,
        "status": status,
        "reason": reason,
    }


# ======================
# LOGGING AND REPORTING
# ======================


def append_signal_log(record: dict[str, Any]) -> bool:
    """Append one unique market/candle decision to the CSV log."""
    path = signal_log_path()
    new_row = pd.DataFrame([record])

    if path.exists():
        existing = pd.read_csv(path)
        if not existing.empty and {"market", "candle_time_utc"}.issubset(existing.columns):
            duplicate = (
                (existing["market"].astype(str) == str(record["market"]))
                & (existing["candle_time_utc"].astype(str) == str(record["candle_time_utc"]))
            ).any()
            if duplicate:
                return False
        new_row.to_csv(path, mode="a", header=False, index=False)
    else:
        new_row.to_csv(path, index=False)

    return True


def format_number(value: Any, digits: int = 4) -> str:
    """Format numeric output while handling missing values."""
    if pd.isna(value):
        return "—"
    return f"{float(value):.{digits}f}"


def print_live_report(record: dict[str, Any], was_logged: bool) -> None:
    """Print a compact paper-trading decision report."""
    print("\n====================================")
    print("PAPER TRADING SIGNAL LOGGER")
    print("====================================")
    print(f"Engine:          {record['engine_version']}")
    print(f"Candle (UTC):    {record['candle_time_utc']}")
    print(f"Market:          {record['market']}")
    print(f"Interval:        {record['interval']}")
    print(f"Close:           {format_number(record['close'])}")
    print(f"Regime:          {record['regime']}")
    print(f"Raw decision:    {record['raw_decision']}")
    print(f"Final decision:  {record['decision']}")
    print(f"Edge score:      {record['edge_score']}")
    print(f"RSI:             {format_number(record['rsi'], 2)}")
    print(f"ATR:             {format_number(record['atr'])}")
    print(f"Status:          {record['status']}")
    print(f"Reason:          {record['reason']}")

    if record["status"] == "QUALIFYING_SIGNAL":
        print("\n--- SIMULATED SETUP ---")
        print(f"Direction:       {record['direction']}")
        print(f"Reference entry: {format_number(record['reference_entry'])}")
        print(f"Stop:            {format_number(record['stop_price'])}")
        print(f"Target:          {format_number(record['target_price'])}")

    print("\nLog result:      " + ("saved" if was_logged else "duplicate candle — not saved again"))
    print(f"CSV location:    {signal_log_path()}")
    print("Real orders:     disabled")
    print("====================================")


# ======================
# MAIN
# ======================


def main() -> None:
    """Run one paper-trading check against the latest completed candle."""
    try:
        df = download_recent_data()
        df = keep_completed_candles(df)
        df = add_features(df)
        df = add_signals(df)

        record = evaluate_latest_candle(df)

        should_log = LOG_WAIT_DECISIONS or record["decision"] != "WAIT"
        was_logged = append_signal_log(record) if should_log else False
        print_live_report(record, was_logged)

        if DEBUG:
            print("\nLatest feature row:")
            columns = [
                "timestamp",
                "Open",
                "High",
                "Low",
                "Close",
                "ma20",
                "ma50",
                "atr",
                "atr_pct",
                "rsi",
                "regime",
                "decision",
                "signal",
            ]
            print(df[columns].tail(1).to_string(index=False))

    except (RuntimeError, ValueError, KeyError, OSError) as exc:
        print("\nPAPER TRADER ERROR")
        print(f"{type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
