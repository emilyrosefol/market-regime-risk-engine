# ============================
# VERSION: FAKE ENGINE V1 CLEAN
# - fake breakouts only
# - range + fake breakout entries
# - ATR stop / take-profit engine
# - trade ledger + V4 R-based accounting
# ============================

import pandas as pd
import numpy as np
from pathlib import Path
import yfinance as yf

# ======================
# CONFIG
# ======================

ENGINE_VERSION = "backtest_v32_edge_discovery"
TICKER = "ETC-USD"
INTERVAL = "1h"
PERIOD = "730d"

ATR_LEN = 14
STOP_ATR = 1.0
TP_ATR = 2.0

FAST_MA = 20
SLOW_MA = 50
CONFIRM_MA = 20

USE_VOL_FILTER = True
VOL_FILTER_LOOKBACK = 50
VOL_EXPANSION_MULT = 1.05

USE_REGIME_FILTER = True
ALLOWED_REGIME = "TREND"

USE_TREND_CONFIRM = True

USE_TREND_STRENGTH_FILTER = True
TREND_STRENGTH_MIN = 0.01

ENTRY_MODEL = "NEXT_OPEN"
SHIFT_SIGNALS_FOR_NEXT_OPEN = True
CONSERVATIVE_IF_BOTH_HIT = True

FEE_PER_TURN = 0.0005
START_EQUITY = 10_000
RISK_UNIT = 0.01
MAX_LEVERAGE = 3.0

MIN_ATR_PCT = 0.001

SAVE_CSV = True
PLOT_EQUITY = False

DEBUG_PRINT_FIRST_N_TRADES = 5
DEBUG_PRINT_FIRST_N_ALLOWS = 10

# Fake/range breakout settings
BUFFER = 0.001
RANGE_LOOKBACK = 20

# ======================
# PATHS
# ======================

def project_root() -> Path:
    return Path(__file__).resolve().parents[0]


def ensure_dirs() -> None:
    (project_root() / "data").mkdir(exist_ok=True)
    (project_root() / "analysis").mkdir(exist_ok=True)


# ======================
# DATA
# ======================

def load_or_download(
    ticker: str = TICKER,
    interval: str = INTERVAL,
    period: str = PERIOD
) -> pd.DataFrame:
    ensure_dirs()

    data_file = project_root() / "data" / f"{ticker.replace('-', '')}_{interval}_{period}_yahoo.csv"

    if data_file.exists():
        df = pd.read_csv(data_file)
    else:
        df = yf.download(tickers=ticker, interval=interval, period=period, auto_adjust=False)

        print("\n=== DATA CHECK ===")
        print("Configured ticker:", TICKER)
        print("Rows loaded:", len(df))
        print("First rows:")
        print(df.head())
        print("Last rows:")
        print(df.tail())

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()
        df.to_csv(data_file, index=False)

    if "Datetime" in df.columns:
        df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")
        df = df.sort_values("Datetime")
    elif "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.sort_values("Date")

    return df.reset_index(drop=True)


def clean_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    needed = ["Open", "High", "Low", "Close"]
    out = df.copy()

    for col in needed:
        if col not in out.columns and col.lower() in out.columns:
            out[col] = out[col.lower()]

    for col in needed:
        if col not in out.columns:
            raise ValueError(f"Missing column '{col}'. Found columns: {list(out.columns)}")

    for col in needed:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.dropna(subset=needed).reset_index(drop=True)
    return out


# ======================
# FEATURES
# ======================

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["ma20"] = df["Close"].rolling(20).mean()
    df["ma50"] = df["Close"].rolling(50).mean()

    df["trend_dir"] = 0
    df.loc[df["ma20"] > df["ma50"], "trend_dir"] = 1
    df.loc[df["ma20"] < df["ma50"], "trend_dir"] = -1

    df["prev_close"] = df["Close"].shift(1)
    df["tr1"] = df["High"] - df["Low"]
    df["tr2"] = (df["High"] - df["prev_close"]).abs()
    df["tr3"] = (df["Low"] - df["prev_close"]).abs()
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)

    df["atr"] = df["tr"].rolling(ATR_LEN).mean()
    df["atr_pct"] = df["atr"] / df["Close"]

    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    df["range_high"] = df["High"].rolling(RANGE_LOOKBACK).max().shift(1)
    df["range_low"] = df["Low"].rolling(RANGE_LOOKBACK).min().shift(1)

    df["ma_gap_pct"] = (df["ma20"] - df["ma50"]).abs() / df["Close"]
    df["atr_pct_mean50"] = df["atr_pct"].rolling(50).mean()

    df["is_range"] = (
        (df["atr_pct"] < df["atr_pct_mean50"]) &
        (df["ma_gap_pct"] < 0.003) &
        (df["rsi"].between(45, 55))
    )

    df["regime"] = "TREND"
    df.loc[df["is_range"], "regime"] = "RANGE"

    df["returns"] = df["Close"].pct_change().fillna(0)

    return df


# ======================
# SIGNALS
# ======================

def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    fake_break_long = (
        (df["regime"] == "RANGE") &
        (df["Low"] < df["range_low"]) &
        (df["Close"] > df["range_low"])
    )

    fake_break_short = (
        (df["regime"] == "RANGE") &
        (df["High"] > df["range_high"]) &
        (df["Close"] < df["range_high"])
    )

    range_long = (
        (df["regime"] == "RANGE") &
        (df["Close"] <= df["range_low"] * (1 + BUFFER)) &
        (df["rsi"] < 50)
    )

    range_short = (
        (df["regime"] == "RANGE") &
        (df["Close"] >= df["range_high"] * (1 - BUFFER)) &
        (df["rsi"] > 50)
    )

    df["decision"] = "WAIT"

    df.loc[fake_break_long & (df["rsi"] < 50), "decision"] = "GO_FAKE_LONG"
    df.loc[fake_break_short & (df["rsi"] > 50), "decision"] = "GO_FAKE_SHORT"

    df.loc[(df["decision"] == "WAIT") & range_long, "decision"] = "GO_RANGE_LONG"
    df.loc[(df["decision"] == "WAIT") & range_short, "decision"] = "GO_RANGE_SHORT"

    df["signal"] = 0
    df.loc[df["decision"].isin(["GO_FAKE_LONG", "GO_RANGE_LONG"]), "signal"] = 1
    df.loc[df["decision"].isin(["GO_FAKE_SHORT", "GO_RANGE_SHORT"]), "signal"] = -1

    df["signal_strength"] = 0
    df.loc[df["decision"].isin(["GO_RANGE_LONG", "GO_RANGE_SHORT"]), "signal_strength"] = 1
    df.loc[df["decision"].isin(["GO_FAKE_LONG", "GO_FAKE_SHORT"]), "signal_strength"] = 3

    return df


# ======================
# EXECUTION ENGINE
# ======================

def run_atr_execution(
    df: pd.DataFrame,
    show_diagnostics: bool = False
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()

    df["position"] = 0
    df["exit_reason"] = None

    trade_rows = []

    in_trade = False
    trade_side = 0
    entry_time = None
    entry_price = None
    entry_atr = None
    stored_entry_signal = None
    stored_entry_rsi = None
    stored_entry_regime = None
    stored_quality_score = None
    stored_entry_range = None
    stored_ma_distance = None
    stop_price = None
    tp_price = None
    bars_held = 0

    total_signals = 0
    passed_signal = 0
    passed_rsi = 0
    passed_atr = 0
    executed_trades = 0

    for i in range(1, len(df)):
        signal = df["signal"].iloc[i]
        high = df["High"].iloc[i]
        low = df["Low"].iloc[i]
        close = df["Close"].iloc[i]
        atr = df["atr"].iloc[i]

        if pd.isna(atr):
            continue



        # ======================
        # ENTRY
        # ======================

        quality_score = 0
        # Trend quality
        if df["trend_dir"].iloc[i] == 1:
            quality_score += 25

        # Strong trend
        if abs(df["ma20"].iloc[i] - df["ma50"].iloc[i]) > df["atr"].iloc[i]:
            quality_score += 20

        # Healthy volatility
        if df["atr_pct"].iloc[i] > df["atr_pct_mean50"].iloc[i]:
            quality_score += 20

        # RSI
        rsi = df["rsi"].iloc[i]
        if 40 <= rsi <= 60:
            quality_score += 15

        # Fake breakout signal
        if signal != 0:
            quality_score += 20
            total_signals += 1

            entry_signal = df["decision"].iloc[i]

            allowed_signal = entry_signal in [
                "GO_FAKE_SHORT",
                "GO_FAKE_LONG",
            ]
            allowed_rsi = 30 <= df["rsi"].iloc[i] <= 60

            atr_pct = df["atr_pct"].iloc[i]

            if pd.isna(atr_pct):
                continue

            allowed_atr = 0.001 <= atr_pct <= 0.01


            if allowed_signal:
                passed_signal += 1

            if allowed_signal and allowed_rsi:
                passed_rsi += 1

            if allowed_signal and allowed_rsi and allowed_atr:
                passed_atr += 1

        if (
                    not in_trade
                    and signal != 0
                    and allowed_signal
                    and allowed_rsi
                    and allowed_atr
            ):
            in_trade = True
            executed_trades += 1
            trade_side = int(signal)
            entry_time = df.index[i]
            entry_price = close
            entry_atr = atr
            stored_entry_signal = entry_signal
            stored_entry_rsi = df["rsi"].iloc[i]
            stored_entry_regime = df["regime"].iloc[i]
            stored_quality_score = quality_score
            stored_entry_range = high - low
            stored_ma_distance = abs(close - df["ma20"].iloc[i])
            bars_held = 0


            if trade_side == 1:
                stop_price = entry_price - (STOP_ATR * atr)
                tp_price = entry_price + (TP_ATR * atr)
                df.at[df.index[i], "position"] = 1
            else:
                stop_price = entry_price + (STOP_ATR * atr)
                tp_price = entry_price - (TP_ATR * atr)
                df.at[df.index[i], "position"] = -1

            continue

        # No open trade
        if not in_trade:
            continue

        bars_held += 1
        exit_price = None
        exit_reason = None

        # ======================
        # MANAGE LONG
        # ======================
        if trade_side == 1:
            stop_hit = low <= stop_price
            tp_hit = high >= tp_price

            if stop_hit and tp_hit:
                exit_price = stop_price
                exit_reason = "STOP_LOSS_BOTH_HIT"
            elif stop_hit:
                exit_price = stop_price
                exit_reason = "STOP_LOSS"
            elif tp_hit:
                exit_price = tp_price
                exit_reason = "TAKE_PROFIT"
            else:
                df.at[df.index[i], "position"] = 1

        # ======================
        # MANAGE SHORT
        # ======================
        elif trade_side == -1:
            stop_hit = high >= stop_price
            tp_hit = low <= tp_price

            if stop_hit and tp_hit:
                exit_price = stop_price
                exit_reason = "STOP_LOSS_BOTH_HIT"
            elif stop_hit:
                exit_price = stop_price
                exit_reason = "STOP_LOSS"
            elif tp_hit:
                exit_price = tp_price
                exit_reason = "TAKE_PROFIT"
            else:
                df.at[df.index[i], "position"] = -1

        # ======================
        # EXIT
        # ======================
        if exit_reason is not None:
            exit_time = df.index[i]
            df.at[df.index[i], "exit_reason"] = exit_reason

            direction = "LONG" if trade_side == 1 else "SHORT"

            if trade_side == 1:
                pnl_pct = (exit_price - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - exit_price) / entry_price * 100

            trade_rows.append({
                "entry_time": entry_time,
                "exit_time": exit_time,
                "direction": direction,

                "entry_price": entry_price,
                "exit_price": exit_price,

                "entry_atr": entry_atr,
                "entry_signal": stored_entry_signal,

                "stop_price": stop_price,
                "tp_price": tp_price,

                "pnl_pct": pnl_pct,
                "bars_held": bars_held,
                "exit_reason": exit_reason,

                "quality_score": stored_quality_score,

                "entry_rsi": stored_entry_rsi,
                "entry_regime": stored_entry_regime,
                "trend_dir": df["trend_dir"].iloc[i],
                "entry_close": df["Close"].iloc[i],
                "entry_range" : stored_entry_range,
                "ma_distance" : stored_ma_distance,
            })

            in_trade = False
            trade_side = 0
            entry_time = None
            entry_price = None
            entry_atr = None
            stop_price = None
            tp_price = None
            bars_held = 0

    if show_diagnostics:
        print("\n=== FILTER DIAGNOSTICS ===")
        print("Signals Found:   ", total_signals)
        print("Passed Signal:   ", passed_signal)
        print("Passed RSI:      ", passed_rsi)
        print("Passed ATR:      ", passed_atr)
        print("Trades Executed: ", executed_trades)

    trade_ledger = pd.DataFrame(trade_rows)
    return df, trade_ledger


# ======================
# V4 REAL TRADE ACCOUNTING
# ======================

def apply_v4_accounting(trade_ledger: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    trade_ledger = trade_ledger.copy()

    equity = START_EQUITY
    running_max_equity = START_EQUITY
    equity_points = []

    if trade_ledger.empty:
        return trade_ledger, pd.DataFrame(equity_points), equity

    trade_ledger["risk_dollars"] = np.nan
    trade_ledger["equity_before"] = np.nan
    trade_ledger["equity_after"] = np.nan
    trade_ledger["pnl_dollars"] = np.nan
    trade_ledger["r_multiple"] = np.nan

    for idx, trade in trade_ledger.iterrows():
        equity_before = equity
        risk_dollars = equity_before * RISK_UNIT

        if trade["exit_reason"] == "TAKE_PROFIT":
            r_multiple = TP_ATR / STOP_ATR
        elif trade["exit_reason"] in ["STOP_LOSS", "STOP_LOSS_BOTH_HIT"]:
            r_multiple = -1
        else:
            r_multiple = 0

        pnl_dollars = risk_dollars * r_multiple
        equity = equity_before + pnl_dollars

        trade_ledger.at[idx, "risk_dollars"] = risk_dollars
        trade_ledger.at[idx, "equity_before"] = equity_before
        trade_ledger.at[idx, "equity_after"] = equity
        trade_ledger.at[idx, "pnl_dollars"] = pnl_dollars
        trade_ledger.at[idx, "r_multiple"] = r_multiple

        running_max_equity = max(running_max_equity, equity)
        drawdown = equity / running_max_equity - 1

        equity_points.append({
            "trade_num": len(equity_points) + 1,
            "equity": equity,
            "drawdown": drawdown,
        })

    equity_curve = pd.DataFrame(equity_points)
    return trade_ledger, equity_curve, equity


# ======================
# REPORTING
# ======================

def print_report(df: pd.DataFrame, trade_ledger: pd.DataFrame, equity_curve: pd.DataFrame, final_equity: float) -> None:
    print("\n==============================")
    print(f"ENGINE VERSION: {ENGINE_VERSION}")
    print("==============================")

    print("\nSignal counts:")
    print(df["signal"].value_counts(dropna=False))

    print("\nDecision counts:")
    print(df["decision"].value_counts(dropna=False))

    print("\nRegime counts:")
    print(df["regime"].value_counts(dropna=False))

    print("\n=== TRADE LEDGER DEBUG ===")
    if trade_ledger.empty:
        print("No completed trades.")
        return

    cols = [
        "direction",
        "entry_price",
        "exit_price",
        "exit_reason",
        "pnl_pct",
        "r_multiple",
        "risk_dollars",
        "pnl_dollars",
        "equity_before",
        "equity_after",
        "bars_held",
    ]

    print(trade_ledger[cols].head(20))

    total_return_pct = ((final_equity / START_EQUITY) - 1) * 100
    max_dd_pct = equity_curve["drawdown"].min() * 100 if not equity_curve.empty else 0
    win_rate = (trade_ledger["r_multiple"] > 0).mean() * 100
    avg_r = trade_ledger["r_multiple"].mean()

    gross_profit = trade_ledger.loc[trade_ledger["pnl_dollars"] > 0, "pnl_dollars"].sum()
    gross_loss = abs(trade_ledger.loc[trade_ledger["pnl_dollars"] < 0, "pnl_dollars"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else np.inf

    print("\n=== V4 EXECUTION ENGINE ===")
    print("Final equity:", round(final_equity, 2))
    print("Total return %:", round(total_return_pct, 2))
    print("Max drawdown %:", round(max_dd_pct, 2))
    print("Total trades:", len(trade_ledger))
    print("Win rate %:", round(win_rate, 2))
    print("Average R:", round(avg_r, 3))
    print("Profit factor:", round(profit_factor, 3))

    print("\nLast 10 equity points:")
    print(equity_curve.tail(10))


def save_outputs(df: pd.DataFrame, trade_ledger: pd.DataFrame, equity_curve: pd.DataFrame) -> None:
    if not SAVE_CSV:
        return

    analysis_dir = project_root() / "analysis"

    df.to_csv(analysis_dir / "fake_engine_v1_clean_output.csv", index=False)
    trade_ledger.to_csv(analysis_dir / "fake_engine_v1_trade_ledger.csv", index=False)
    equity_curve.to_csv(analysis_dir / "fake_engine_v1_equity_curve.csv", index=False)

    print("\nSaved CSVs to /analysis")


# ======================
# MAIN
# ======================

#def main() -> None:
#    df = load_or_download()
#   df = clean_ohlc(df)
#    df = add_features(df)
#    df = add_signals(df)

#    df, trade_ledger = run_atr_execution(df)

#    trade_ledger, equity_curve, final_equity = apply_v4_accounting(trade_ledger)

#    print_report(df, trade_ledger, equity_curve, final_equity)

#    save_outputs(df, trade_ledger, equity_curve)

def main() -> None:
    df = load_or_download()

    print("\n=== DATA CHECK ===")
    print("Configured ticker:", TICKER)
    print("Rows loaded:", len(df))
    
    df = clean_ohlc(df)
    df = add_features(df)
    df = add_signals(df)

    df, trade_ledger = run_atr_execution(df, show_diagnostics=True)

    df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")

    def yearly_metrics(trades: pd.DataFrame) -> dict:
        if trades.empty:
            return {
                "trades": 0,
                "return_pct": 0.0,
                "max_dd_pct": 0.0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
            }

        trades, equity_curve, final_equity = apply_v4_accounting(trades)

        return_pct = ((final_equity / START_EQUITY) - 1) * 100
        max_dd_pct = equity_curve["drawdown"].min() * 100 if not equity_curve.empty else 0
        win_rate_pct = (trades["r_multiple"] > 0).mean() * 100

        gross_profit = trades.loc[trades["pnl_dollars"] > 0, "pnl_dollars"].sum()
        gross_loss = abs(trades.loc[trades["pnl_dollars"] < 0, "pnl_dollars"].sum())
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else np.inf

        return {
            "trades": len(trades),
            "return_pct": return_pct,
            "max_dd_pct": max_dd_pct,
            "win_rate_pct": win_rate_pct,
            "profit_factor": profit_factor,
        }

    print("\n========================")
    print("YEARLY VALIDATION")
    print("========================")

    years = sorted(df["Datetime"].dt.year.dropna().unique())

    for year in years:

        yearly_df = df[df["Datetime"].dt.year == year].copy()

        if len(yearly_df) < 500:
            continue

        yearly_df, yearly_trades = run_atr_execution(yearly_df)

        metrics = yearly_metrics(yearly_trades)

        print(f"\n===== {year} =====")
        print(f"Trades:        {metrics['trades']}")
        print(f"Return %:      {metrics['return_pct']:.2f}")
        print(f"Max DD %:      {metrics['max_dd_pct']:.2f}")
        print(f"Win Rate %:    {metrics['win_rate_pct']:.2f}")
        print(f"Profit Factor: {metrics['profit_factor']:.3f}")

    # Walk-forward split
    split_idx = int(len(df) * 0.70)

    in_sample = df.iloc[:split_idx].copy()
    out_sample = df.iloc[split_idx:].copy()

    def filter_trades_by_sample(trades, start_idx, end_idx):
        return trades[
            (trades["entry_time"] >= start_idx) &
            (trades["entry_time"] < end_idx)
            ].copy()

    def sample_stats(name, trades):
        if trades.empty:
            print(f"{name}: No trades")
            return

        temp, eq, final_eq = apply_v4_accounting(trades)
        ret_pct = ((final_eq / START_EQUITY) - 1) * 100
        max_dd = eq["drawdown"].min() * 100 if not eq.empty else 0
        win_rate = (temp["r_multiple"] > 0).mean() * 100
        pf = (
                temp.loc[temp["pnl_dollars"] > 0, "pnl_dollars"].sum()
                / abs(temp.loc[temp["pnl_dollars"] < 0, "pnl_dollars"].sum())
        )

        print(f"{name} return %: {ret_pct:.2f}")
        print(f"{name} maxDD %: {max_dd:.2f}")
        print(f"{name} trades: {len(temp)}")
        print(f"{name} win rate %: {win_rate:.2f}")
        print(f"{name} profit factor: {pf:.3f}")

    trade_ledger, equity_curve, final_equity = apply_v4_accounting(trade_ledger)

    print_report(df, trade_ledger, equity_curve, final_equity)

    if trade_ledger.empty:
        save_outputs(df, trade_ledger, equity_curve)
        return

    print("\n=== QUALITY SCORE ANALYSIS ===")

    print(
        trade_ledger.groupby("quality_score")["pnl_pct"]
        .agg(["count", "mean", "median"])
    )

    print("\nTrade ledger columns:")
    print(trade_ledger.columns.tolist())

    print("\n=== REGIME ANALYSIS ===")

    print(
        trade_ledger.groupby("entry_regime")["pnl_pct"]
        .agg(["count", "mean", "median"])
    )

    print("\n=== DIRECTION ANALYSIS ===")

    print(
        trade_ledger.groupby("direction")["pnl_pct"]
        .agg(["count", "mean"])
    )



    print("\n=== WALK FORWARD ===")

    in_trades = filter_trades_by_sample(trade_ledger, 0, split_idx)
    out_trades = filter_trades_by_sample(trade_ledger, split_idx, len(df))

    sample_stats("IN-SAMPLE", in_trades)
    sample_stats("OUT-SAMPLE", out_trades)

    trade_ledger.groupby("entry_regime")["pnl_pct"].describe()

    trade_ledger.groupby("trend_dir")["pnl_pct"].describe()

    trade_ledger.groupby("bars_held")["pnl_pct"].mean()

    print("\n=== RSI BUCKET ANALYSIS ===")

    trade_ledger["rsi_bucket"] = pd.cut(
        trade_ledger["entry_rsi"],
        bins=[0, 30, 40, 50, 60, 70, 100],
        labels=["0-30", "30-40", "40-50", "50-60", "60-70", "70+"],
        include_lowest=True
    )

    print(
        trade_ledger.groupby("rsi_bucket")["pnl_pct"]
        .agg(["count", "mean", "median"])
    )

    print("\n=== ATR BUCKET ANALYSIS ===")

    trade_ledger["atr_bucket"] = pd.cut(
        trade_ledger["entry_atr"],
        bins=[0, 250, 500, 750, 1000, 100000],
        labels=["0-250", "250-500", "500-750", "750-1000", "1000+"],
        include_lowest=True
    )

    print(
        trade_ledger.groupby("atr_bucket")["pnl_pct"]
        .agg(["count", "mean", "median"])
    )

    print("\n=== HOLD TIME ANALYSIS ===")

    print(
        trade_ledger.groupby("bars_held")["pnl_pct"]
        .agg(["count", "mean", "median"])
    )

    print("\n=== SIGNAL TYPE ANALYSIS ===")

    print(
        trade_ledger.groupby("entry_signal")["pnl_pct"]
        .agg(["count", "mean", "median"])
    )

    print("\n=== ENTRY RANGE ANALYSIS ===")

    trade_ledger["entry_range_bucket"] = pd.qcut(
        trade_ledger["entry_range"],
        q=3,
        labels=["SMALL", "MEDIUM", "LARGE"],
        duplicates="drop",
    )

    print(
        trade_ledger.groupby("entry_range_bucket", observed=True)["pnl_pct"]
        .agg(["count", "mean", "median"])
    )

    print("\n=== MA DISTANCE ANALYSIS ===")

    trade_ledger["ma_bucket"] = pd.qcut(
        trade_ledger["ma_distance"],
        q=3,
        labels=["LOW", "MEDIUM", "HIGH"],
        duplicates="drop",
    )

    print(
        trade_ledger.groupby("ma_bucket", observed=True)["pnl_pct"]
        .agg(["count", "mean", "median"])
    )

    print("\n=== RANGE + MA COMBINATION ===")

    combo = (
        trade_ledger
        .groupby(
            ["entry_range_bucket", "ma_bucket"],
            observed=True
        )["pnl_pct"]
        .agg(["count", "mean", "median"])
    )

    print(combo)

    save_outputs(df, trade_ledger, equity_curve)

if __name__ == "__main__":
    main()