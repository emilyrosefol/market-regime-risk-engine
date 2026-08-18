# ============================
# VERSION: FAKE ENGINE V1
# - fake breakouts only
# - buffer = 0.0008
# - ffill limit = 6
# ============================

# ======================
# CONFIG
# ======================

import pandas as pd
import numpy as np
from pathlib import Path

ENGINE_VERSION = "v2_clean_dual_next_open"

TICKER = "BTC-USD"
INTERVAL = "1h"
PERIOD = "730d"

ATR_LEN = 14
STOP_ATR = 1.5
TP_ATR = 3.0

FEE_PER_TURN = 0.0005
RISK_UNIT = 0.01
MAX_LEVERAGE = 3.0
MIN_ATR_PCT = 0.001

USE_VOL_FILTER = True
VOL_FILTER_LOOKBACK = 50
VOL_EXPANSION_MULT = 1.05

USE_REGIME_FILTER = True
ALLOWED_REGIME = "TREND"

USE_TREND_CONFIRM = True
FAST_MA = 20
SLOW_MA = 50
CONFIRM_MA = 20

USE_TREND_STRENGTH_FILTER = True
TREND_STRENGTH_MIN = 0.005

ENTRY_MODEL = "NEXT_OPEN"   # "NEXT_OPEN" or "CLOSE"
SHIFT_SIGNALS_FOR_NEXT_OPEN = True
CONSERVATIVE_IF_BOTH_HIT = True

SAVE_CSV = True
PLOT_EQUITY = True

DEBUG_PRINT_FIRST_N_TRADES = 5
DEBUG_PRINT_FIRST_N_ALLOWS = 10


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
        df = yf.download(tickers=ticker, interval=interval, period=period)
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
            raise ValueError(f"Missing column '{col}'. Found: {list(out.columns)}")

    for col in needed:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.dropna(subset=needed).reset_index(drop=True)
    return out

if __name__ == "__main__":
        df = load_or_download()
        df = clean_ohlc(df)

        df["ma20"] = df["Close"].rolling(20).mean()
        df["ma50"] = df["Close"].rolling(50).mean()

        df["trend_dir"] = 0
        df.loc[df["ma20"] > df["ma50"], "trend_dir"] = 1
        df.loc[df["ma20"] < df["ma50"], "trend_dir"] = -1

        delta = df["Close"].diff()

        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()

        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        df["prev_close"] = df["Close"].shift(1)
        df["tr1"] = df["High"] - df["Low"]
        df["tr2"] = (df["High"] - df["prev_close"]).abs()
        df["tr3"] = (df["Low"] - df["prev_close"]).abs()

        df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
        df["atr"] = df["tr"].rolling(14).mean()
        df["atr_pct"] = df["atr"] / df["Close"]

        delta = df["Close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()

        rs = avg_gain / avg_loss
        df["rsi"] = 100 - (100 / (1 + rs))

        df["range_high"] = df["High"].rolling(20).max().shift(1)
        df["range_low"] = df["Low"].rolling(20).min().shift(1)

        df["ma_gap_pct"] = (df["ma20"] - df["ma50"]).abs() / df["Close"]
        df["atr_pct_mean50"] = df["atr_pct"].rolling(50).mean()

df["is_range"] = (
        (df["atr_pct"] < df["atr_pct_mean50"]) &
        (df["ma_gap_pct"] < 0.003) &
        (df["rsi"].between(45,55))
)

df["regime"] = "TREND"
df.loc[df["is_range"], "regime"] = "RANGE"

buffer = 0.001

# --- FAKE BREAKOUT LOGIC ---
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

# --- DECISION LOGIC ---
df["decision"] = "WAIT"

df.loc[fake_break_long & (df["rsi"] < 50), "decision"] = "GO_FAKE_LONG"
df.loc[fake_break_short & (df["rsi"] > 50), "decision"] = "GO_FAKE_SHORT"

range_long = (
        (df["regime"] == "RANGE") &
        (df["Close"] <= df["range_low"] * (1 + buffer)) &
        (df["rsi"] < 50)
)

range_short = (
        (df["regime"] == "RANGE") &
        (df["Close"] >= df["range_high"] * (1 - buffer)) &
        (df["rsi"] > 50)
)

df.loc[(df["decision"] == "WAIT") & range_long, "decision"] = "GO_RANGE_LONG"
df.loc[(df["decision"] == "WAIT") & range_short, "decision"] = "GO_RANGE_SHORT"

# --- SIGNAL (direction) ---
df["signal"] = 0
df.loc[df["decision"].isin(["GO_FAKE_LONG", "GO_RANGE_LONG"]), "signal"] = 1
df.loc[df["decision"].isin(["GO_FAKE_SHORT", "GO_RANGE_SHORT"]), "signal"] = -1

print("Signal counts:")
print(df["signal"].value_counts(dropna=False))

trade_count = (df["signal"] != 0).sum()

print(f"Total trades: {trade_count}")

if trade_count == 0:
    print("⚠️ No trades generated")
    # raise SystemExit

# --- SIGNAL STRENGTH ---
df["signal_strength"] = 0
df.loc[df["decision"].isin(["GO_RANGE_LONG", "GO_RANGE_SHORT"]), "signal_strength"] = 1
df.loc[df["decision"].isin(["GO_FAKE_LONG", "GO_FAKE_SHORT"]), "signal_strength"] = 3
 #df["position"] = df["signal"].replace(0, pd.NA)
 #df["position"] = df["position"].ffill(limit=7).fillna(0)

# --- REAL ATR EXIT ENGINE ---
df["position"] = 0
df["exit_reason"] = None

in_trade = False
trade_side = 0
entry_price = None
stop_price = None
tp_price = None

for i in range(1, len(df)):

    signal = df["signal"].iloc[i]
    high = df["High"].iloc[i]
    low = df["Low"].iloc[i]
    close = df["Close"].iloc[i]
    atr = df["atr"].iloc[i]

    if pd.isna(atr):
        continue

    # ENTER LONG
    if not in_trade and signal == 1:
        in_trade = True
        trade_side = 1
        entry_price = close
        stop_price = entry_price - (STOP_ATR * atr)
        tp_price = entry_price + (TP_ATR * atr)
        df.at[df.index[i], "position"] = 1
        continue

    # ENTER SHORT
    if not in_trade and signal == -1:
        in_trade = True
        trade_side = -1
        entry_price = close
        stop_price = entry_price + (STOP_ATR * atr)
        tp_price = entry_price - (TP_ATR * atr)
        df.at[df.index[i], "position"] = -1
        continue

    # MANAGE LONG
    if in_trade and trade_side == 1:
        if low <= stop_price:
            df.at[df.index[i], "exit_reason"] = "STOP_LOSS"
            in_trade = False
            trade_side = 0
        elif high >= tp_price:
            df.at[df.index[i], "exit_reason"] = "TAKE_PROFIT"
            in_trade = False
            trade_side = 0
        else:
            df.at[df.index[i], "position"] = 1

    # MANAGE SHORT
    if in_trade and trade_side == -1:
        if high >= stop_price:
            df.at[df.index[i], "exit_reason"] = "STOP_LOSS"
            in_trade = False
            trade_side = 0
        elif low <= tp_price:
            df.at[df.index[i], "exit_reason"] = "TAKE_PROFIT"
            in_trade = False
            trade_side = 0
        else:
            df.at[df.index[i], "position"] = -1


# --- RETURNS ---
df["returns"] = df["Close"].pct_change()

# Shift position so you enter NEXT bar (realistic execution)
df["strategy_return"] = df["position"].shift(1) * df["returns"]
fee_per_trade = 0.0005
df["turnover"] = df["position"].diff().abs().fillna(0)
df["strategy_return"] = df["strategy_return"] - (df["turnover"] * fee_per_trade)

# Fill NaN
df["strategy_return"] = df["strategy_return"].fillna(0)

# --- SIMPLE TRADE LEDGER ---
trade_rows = []
in_trade = False

entry_time = None
entry_price = None
entry_direction = None
bars_held = 0

for i in range(1, len(df)):
    current_pos = df["position"].iloc[i]
    prev_pos = df["position"].iloc[i - 1]

    # trade opens
    if prev_pos == 0 and current_pos != 0:
        in_trade = True
        entry_time = df.index[i]
        entry_price = df["Close"].iloc[i]
        entry_direction = "LONG" if current_pos == 1 else "SHORT"
        bars_held = 0

    # trade is open
    if in_trade:
        bars_held += 1

    # trade closes
    if in_trade and current_pos == 0 and prev_pos != 0:
        exit_time = df.index[i]
        exit_price = df["Close"].iloc[i]

        if entry_direction == "LONG":
            pnl_pct = (exit_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - exit_price) / entry_price * 100

        trade_rows.append({
            "entry_time": entry_time,
            "exit_time": exit_time,
            "direction": entry_direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl_pct": pnl_pct,
            "bars_held": bars_held,
            "exit_reason": df["exit_reason"].iloc[i]
        })

        in_trade = False

trade_ledger = pd.DataFrame(trade_rows)

print("\n=== TRADE LEDGER DEBUG ===")
print(trade_ledger.head(20))
print("\nTotal ledger trades:", len(trade_ledger))

if len(trade_ledger) > 0:
    print("Win rate %:", (trade_ledger["pnl_pct"] > 0).mean() * 100)
    print("Average PnL %:", trade_ledger["pnl_pct"].mean())
    print("Best trade %:", trade_ledger["pnl_pct"].max())
    print("Worst trade %:", trade_ledger["pnl_pct"].min())


# --- EQUITY CURVE ---
df["equity_curve"] = (1 + df["strategy_return"]).cumprod()
df["peak_equity"] = df["equity_curve"].cummax()
df["drawdown"] = df["equity_curve"] / df["peak_equity"] - 1

max_dd = df["drawdown"].min()

print("\n=== TREND DEBUG ===")
print(df["trend_dir"].value_counts())

print("\n=== PERFORMANCE DEBUG ===")
print("Final equity:", df["equity_curve"].iloc[-1])
print("Total return %:", (df["equity_curve"].iloc[-1] - 1) * 100)
print("Max drawdown %:", max_dd * 100)

print("\nLast rows:")
print(df[["Close", "position", "returns", "strategy_return", "equity_curve", "drawdown"]].tail(10))

print("=== END PERFORMANCE ===\n")

raise SystemExit


def compute_atr(price: pd.DataFrame, length: int = ATR_LEN) -> pd.Series:
    high = price["High"]
    low = price["Low"]
    close = price["Close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(length).mean()


# ======================
# TRADE LOG
# ======================
def build_trade_log(result: pd.DataFrame) -> pd.DataFrame:
    if "position" not in result.columns:
        raise ValueError("result must include 'position' column")

    df = result.copy()
    pos = df["position"].fillna(0.0).astype(float)
    pos_prev = pos.shift(1).fillna(0.0)

    entry_sig = (pos_prev == 0.0) & (pos != 0.0)
    exit_sig = (pos_prev != 0.0) & (pos == 0.0)

    if "open" in df.columns:
        px = df["open"].astype(float)
    elif "Open" in df.columns:
        px = df["Open"].astype(float)
    elif "close" in df.columns:
        px = df["close"].astype(float)
    else:
        px = df["Close"].astype(float)

    trades = []
    cur = None
    trade_id = 0

    for i in range(len(df)):
        if cur is None and entry_sig.iloc[i]:
            trade_id += 1
            cur = {
                "trade_id": trade_id,
                "direction": "LONG" if pos.iloc[i] == 1.0 else "SHORT",
                "entry_idx": i,
                "entry_price": float(px.iloc[i]),
            }
            continue

        if cur is not None and exit_sig.iloc[i]:
            exit_price = float(px.iloc[i])
            entry_price = float(cur["entry_price"])
            direction = cur["direction"]

            if direction == "LONG":
                pnl = (exit_price / entry_price) - 1.0
            else:
                pnl = (entry_price / exit_price) - 1.0

            cur.update({
                "exit_idx": i,
                "exit_price": exit_price,
                "pnl": pnl,
                "pnl_pct": pnl * 100.0,
                "win": pnl > 0,
            })
            trades.append(cur)
            cur = None

    if not trades:
        return pd.DataFrame(columns=[
            "trade_id", "direction", "entry_idx", "entry_price",
            "exit_idx", "exit_price", "pnl", "pnl_pct", "win"
        ])

    return pd.DataFrame(trades)


# ======================
# PRINTS
# ======================
def print_engine_signal(result: pd.DataFrame, account_size: float = 10_000.0) -> None:
    last = result.iloc[-1]

    close = float(last["close"])
    regime = str(last["regime"])
    decision = str(last["decision"])
    trend_dir = int(last["trend_dir"])
    position = float(last["position"])

    risk_dollars = float(account_size) * float(RISK_UNIT)

    if position == 1.0:
        action = "HOLD LONG"
        paper = "NO (already in position)"
    elif position == -1.0:
        action = "HOLD SHORT"
        paper = "NO (already in position)"
    else:
        bias = "LONG" if trend_dir == 1 else ("SHORT" if trend_dir == -1 else "FLAT")
        if decision == "GO" and bias in ("LONG", "SHORT"):
            action = f"ARM ENTRY {bias}"
            paper = f"YES — PAPER {bias} (risk ${risk_dollars:,.2f})"
        else:
            action = "WAIT / NO TRADE"
            paper = "NO"

    print("\n==============================")
    print("ENGINE DAILY SIGNAL")
    print("==============================")
    print(f"Price:    {close:,.2f}")
    print(f"Regime:   {regime}")
    print(f"Decision: {decision}")
    print(f"TrendDir: {trend_dir}")
    print(f"Position: {position}")
    print(f"Action:   {action}")
    print(f"Paper?:   {paper}")
    print(f"Risk:     ${risk_dollars:,.2f}")
    print("==============================\n")


def print_pro_metrics(result: pd.DataFrame, trade_log: pd.DataFrame) -> None:
    ret = result["strategy_return"].fillna(0.0)
    std = ret.std()
    sharpe = (ret.mean() / std) * np.sqrt(252 * 24) if std != 0 else 0.0
    max_dd = result["dd"].min()
    exposure = (result["position"].abs() > 0).mean()

    print("\n=== PRO METRICS ===")
    print(f"Sharpe (annualized): {sharpe:.3f}")
    print(f"Max Drawdown: {max_dd * 100:.2f}%")
    print(f"Exposure: {exposure * 100:.1f}%")

    if trade_log is None or trade_log.empty:
        print("Trades: 0")
        print("No completed trades.")
        return

    pnl = trade_log["pnl_pct"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    profit_factor = (wins.sum() / abs(losses.sum())) if len(losses) else np.nan

    print(f"Trades: {len(pnl)}")
    print(f"Win rate: {(pnl > 0).mean() * 100:.1f}%")
    print(f"Avg win: {wins.mean():.3f}%")
    print(f"Avg loss: {losses.mean():.3f}%")
    print(f"Profit factor: {profit_factor:.3f}")
    print(f"Expectancy/trade: {pnl.mean():.3f}%")


# ======================
# HELPERS
# ======================
def force_flat_at_end(result: pd.DataFrame) -> pd.DataFrame:
    if len(result) > 1 and result["position"].iloc[-1] != 0:
        last_pos = float(result["position"].iloc[-1])
        last_close = float(result["close"].iloc[-1])
        prev_close = float(result["close"].iloc[-2])
        size = float(result["position_size"].iloc[-1])
        rm = float(result["risk_multiplier"].iloc[-1])

        move = (last_close / prev_close) - 1.0
        extra_ret = last_pos * size * move * rm - FEE_PER_TURN

        result.loc[result.index[-1], "strategy_return"] += extra_ret
        result.loc[result.index[-1], "position"] = 0.0

    result["equity_curve"] = (1.0 + result["strategy_return"]).cumprod()
    result["dd"] = result["equity_curve"] / result["equity_curve"].cummax() - 1.0
    return result


def rolling_walk_forward_stats(result: pd.DataFrame, n_splits: int = 4) -> pd.DataFrame:
    rows = []
    n = len(result)

    if n < 100:
        print("Not enough rows for rolling walk-forward.")
        return pd.DataFrame()

    chunk = n // (n_splits + 1)

    for i in range(n_splits):
        train_end = chunk * (i + 1)
        test_start = train_end
        test_end = min(train_end + chunk, n)

        train_df = result.iloc[:train_end].copy()
        test_df = result.iloc[test_start:test_end].copy()

        if len(test_df) < 10:
            continue

        train_eq = (1.0 + train_df["strategy_return"]).cumprod()
        test_eq = (1.0 + test_df["strategy_return"]).cumprod()

        train_ret = (train_eq.iloc[-1] - 1.0) * 100.0
        test_ret = (test_eq.iloc[-1] - 1.0) * 100.0

        train_dd = (train_eq / train_eq.cummax() - 1.0).min() * 100.0
        test_dd = (test_eq / test_eq.cummax() - 1.0).min() * 100.0

        train_std = train_df["strategy_return"].std()
        test_std = test_df["strategy_return"].std()

        train_sharpe = (
            train_df["strategy_return"].mean() / train_std * np.sqrt(252 * 24)
            if train_std != 0 else 0.0
        )
        test_sharpe = (
            test_df["strategy_return"].mean() / test_std * np.sqrt(252 * 24)
            if test_std != 0 else 0.0
        )

        test_vol = test_df["close"].pct_change().std()
        test_trend_strength = (
            (test_df["close"].rolling(20).mean() - test_df["close"].rolling(50).mean()).abs()
            / test_df["close"]
        ).mean()

        print(f"\n--- SPLIT {i + 1} ---")
        print("Train rows:", len(train_df))
        print("Test rows:", len(test_df))
        print(f"Train return %: {train_ret:.2f}")
        print(f"Test return %: {test_ret:.2f}")
        print(f"Train Sharpe: {train_sharpe:.3f}")
        print(f"Test Sharpe: {test_sharpe:.3f}")
        print(f"Train MaxDD %: {train_dd:.2f}")
        print(f"Test MaxDD %: {test_dd:.2f}")
        print(f"Test volatility: {test_vol:.6f}")
        print(f"Test trend strength: {test_trend_strength:.6f}")

        rows.append({
            "split": i + 1,
            "train_rows": len(train_df),
            "test_rows": len(test_df),
            "train_return_pct": train_ret,
            "test_return_pct": test_ret,
            "train_maxdd_pct": train_dd,
            "test_maxdd_pct": test_dd,
            "train_sharpe": train_sharpe,
            "test_sharpe": test_sharpe,
            "test_volatility": test_vol,
            "test_trend_strength": test_trend_strength,
        })

    return pd.DataFrame(rows)


# ======================
# BACKTEST
# ======================
def run_backtest(price: pd.DataFrame) -> pd.DataFrame:
    close = price["Close"].astype(float)
    high = price["High"].astype(float)
    low = price["Low"].astype(float)
    open_ = price["Open"].astype(float)

    atr = compute_atr(price, ATR_LEN)

    fast = close.rolling(FAST_MA).mean()
    slow = close.rolling(SLOW_MA).mean()
    trend_dir = np.where(fast > slow, 1, -1)

    ma_confirm = close.rolling(CONFIRM_MA).mean()
    confirm_long = (close > ma_confirm).fillna(False)
    confirm_short = (close < ma_confirm).fillna(False)

    trend_strength = (fast - slow).abs() / close.replace(0, np.nan)
    if USE_TREND_STRENGTH_FILTER:
        trend_strength_ok = (trend_strength > TREND_STRENGTH_MIN).fillna(False)
    else:
        trend_strength_ok = pd.Series(True, index=price.index)

    regimes = classify_regimes(close)
    decisions = [decision_gate(r) for r in regimes]
    decision_df = pd.DataFrame(decisions)

    if "decision" not in decision_df.columns:
        raise ValueError("decision_gate must return dict with key 'decision'")

    if "risk_multiplier" not in decision_df.columns:
        decision_df["risk_multiplier"] = [
            float(get_risk_multiplier(reg, dec))
            for reg, dec in zip(regimes, decision_df["decision"])
        ]

    result = pd.DataFrame({
        "open": open_.values,
        "high": high.values,
        "low": low.values,
        "close": close.values,
        "ATR": atr.values,
        "regime": regimes,
        "trend_dir": trend_dir,
    })

    result = pd.concat([result, decision_df], axis=1)

    result["atr_pct"] = (result["ATR"] / result["close"]).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    if USE_VOL_FILTER:
        base = result["atr_pct"].rolling(VOL_FILTER_LOOKBACK).mean()
        result["vol_filter"] = result["atr_pct"] > (base * VOL_EXPANSION_MULT)
    else:
        result["vol_filter"] = True

    atr_pct_safe = result["atr_pct"].clip(lower=MIN_ATR_PCT)
    result["position_size"] = (RISK_UNIT / atr_pct_safe).clip(upper=MAX_LEVERAGE)

    if ENTRY_MODEL == "NEXT_OPEN" and SHIFT_SIGNALS_FOR_NEXT_OPEN:
        result["decision_sig"] = result["decision"].shift(1)
        result["prev_decision_sig"] = result["decision"].shift(2)
        result["risk_multiplier_sig"] = result["risk_multiplier"].shift(1)
        result["trend_dir_sig"] = result["trend_dir"].shift(1)
        result["vol_filter_sig"] = result["vol_filter"].shift(1)
        result["regime_sig"] = result["regime"].shift(1)
        result["confirm_long_sig"] = confirm_long.shift(1)
        result["confirm_short_sig"] = confirm_short.shift(1)
        result["trend_strength_ok_sig"] = trend_strength_ok.shift(1)
    else:
        result["decision_sig"] = result["decision"]
        result["prev_decision_sig"] = result["decision"].shift(1)
        result["risk_multiplier_sig"] = result["risk_multiplier"]
        result["trend_dir_sig"] = result["trend_dir"]
        result["vol_filter_sig"] = result["vol_filter"]
        result["regime_sig"] = result["regime"]
        result["confirm_long_sig"] = confirm_long
        result["confirm_short_sig"] = confirm_short
        result["trend_strength_ok_sig"] = trend_strength_ok

    sim_pos = 0
    pending_entry = 0
    entry_price = np.nan
    stop_price = np.nan
    tp_price = np.nan

    equity = 1.0
    max_equity = 1.0

    strategy_returns = []
    position_series = []

    debug_allows = 0
    debug_exits = 0

    for i in range(len(result)):
        o = float(result["open"].iloc[i])
        h = float(result["high"].iloc[i])
        l = float(result["low"].iloc[i])
        c = float(result["close"].iloc[i])
        atr_i = result["ATR"].iloc[i]

        if i == 0 or pd.isna(atr_i):
            strategy_returns.append(0.0)
            position_series.append(float(sim_pos))
            continue

        prev_close = float(result["close"].iloc[i - 1])

        decision = str(result["decision_sig"].iloc[i]) if not pd.isna(result["decision_sig"].iloc[i]) else "WAIT"
        td = int(result["trend_dir_sig"].iloc[i]) if not pd.isna(result["trend_dir_sig"].iloc[i]) else 0
        rm = float(result["risk_multiplier_sig"].iloc[i]) if not pd.isna(result["risk_multiplier_sig"].iloc[i]) else 0.0
        size = float(result["position_size"].iloc[i])



        regime_ok = (
            True if not USE_REGIME_FILTER
            else (str(result["regime_sig"].iloc[i]) == str(ALLOWED_REGIME))
        )

        vol_ok = (
            bool(result["vol_filter_sig"].iloc[i])
            if "vol_filter_sig" in result.columns and not pd.isna(result["vol_filter_sig"].iloc[i])
            else True
        )

        strength_ok = (
            bool(result["trend_strength_ok_sig"].iloc[i])
            if "trend_strength_ok_sig" in result.columns and not pd.isna(result["trend_strength_ok_sig"].iloc[i])
            else True
        )

        if USE_TREND_CONFIRM:
            if td == 1:
                trend_ok = bool(result["confirm_long_sig"].iloc[i])
            elif td == -1:
                trend_ok = bool(result["confirm_short_sig"].iloc[i])
            else:
                trend_ok = False
        else:
            trend_ok = True

        trade_allowed = (
            (decision == "GO") and
            (rm >= 0.999) and
            bool(regime_ok) and
            bool(trend_ok) and
            bool(vol_ok) and
            bool(strength_ok) and
            (td in (1, -1)) and
            (result["ATR"].iloc[i] > 0) and
            (size > 0) and
            (sim_pos == 0)
        )

        if trade_allowed and debug_allows < DEBUG_PRINT_FIRST_N_ALLOWS:
            print(
                f"[ALLOW] i={i} decision={decision} "
                F"td{td} "
                f"regime_ok={regime_ok} trend_ok={trend_ok} "
                f"vol_ok={vol_ok} strength_ok={strength_ok} "
                f"rm={rm:.3f} size={size:.3f}"
            )
            debug_allows += 1

        bar_ret = 0.0

        entered_this_bar = False
        if sim_pos == 0 and pending_entry != 0:
            sim_pos = int(pending_entry)
            entry_price = o if ENTRY_MODEL == "NEXT_OPEN" else c
            stop_price = entry_price - STOP_ATR * atr_i if sim_pos == 1 else entry_price + STOP_ATR * atr_i
            tp_price = entry_price + TP_ATR * atr_i if sim_pos == 1 else entry_price - TP_ATR * atr_i
            bar_ret -= FEE_PER_TURN
            pending_entry = 0
            entered_this_bar = True

        base_price = entry_price if (sim_pos != 0 and entered_this_bar) else prev_close

        exited = False
        exit_price = None

        if sim_pos != 0:
            if sim_pos == 1:
                if o <= stop_price:
                    exited, exit_price = True, o
                elif o >= tp_price:
                    exited, exit_price = True, o
            else:
                if o >= stop_price:
                    exited, exit_price = True, o
                elif o <= tp_price:
                    exited, exit_price = True, o

            if not exited:
                if sim_pos == 1:
                    stop_hit = l <= stop_price
                    tp_hit = h >= tp_price

                    if stop_hit and tp_hit:
                        exit_price = float(stop_price) if CONSERVATIVE_IF_BOTH_HIT else float(tp_price)
                        exited = True
                    elif stop_hit:
                        exit_price, exited = float(stop_price), True
                    elif tp_hit:
                        exit_price, exited = float(tp_price), True
                else:
                    stop_hit = h >= stop_price
                    tp_hit = l <= tp_price

                    if stop_hit and tp_hit:
                        exit_price = float(stop_price) if CONSERVATIVE_IF_BOTH_HIT else float(tp_price)
                        exited = True
                    elif stop_hit:
                        exit_price, exited = float(stop_price), True
                    elif tp_hit:
                        exit_price, exited = float(tp_price), True

        if sim_pos != 0 and exited:
            move = (float(exit_price) / float(base_price)) - 1.0
            bar_ret += sim_pos * size * move * rm
            bar_ret -= FEE_PER_TURN

            if debug_exits < DEBUG_PRINT_FIRST_N_TRADES:
                print(
                    f"[EXIT] i={i} pos={sim_pos} base={base_price:.2f} "
                    f"exit={float(exit_price):.2f} ret={bar_ret:.6f}"
                )
                debug_exits += 1

            sim_pos = 0
            entry_price = np.nan
            stop_price = np.nan
            tp_price = np.nan

        elif sim_pos != 0:
            move = (c / prev_close) - 1.0
            bar_ret += sim_pos * size * move * rm

        if sim_pos == 0 and pending_entry == 0 and trade_allowed:
            if ENTRY_MODEL == "NEXT_OPEN":
                pending_entry = td
                if debug_allows <= DEBUG_PRINT_FIRST_N_TRADES:
                    print(
                        f"[ARM ] i={i} td={td} decision={decision} rm={rm} "
                        f"regime_ok={regime_ok} trend_ok={trend_ok} vol_ok={vol_ok}"
                    )
            else:
                sim_pos = td
                entry_price = c
                stop_price = entry_price - STOP_ATR * atr_i if sim_pos == 1 else entry_price + STOP_ATR * atr_i
                tp_price = entry_price + TP_ATR * atr_i if sim_pos == 1 else entry_price - TP_ATR * atr_i
                bar_ret -= FEE_PER_TURN

        equity *= (1.0 + bar_ret)
        max_equity = max(max_equity, equity)

        strategy_returns.append(bar_ret)
        position_series.append(float(sim_pos))

    result["position"] = position_series
    result["strategy_return"] = strategy_returns
    result["equity_curve"] = (1.0 + result["strategy_return"]).cumprod()
    result["dd"] = result["equity_curve"] / result["equity_curve"].cummax() - 1.0

    result = force_flat_at_end(result)
    return result


# ======================
# MAIN
# ======================
def main() -> None:
    print(f"\n=== Running {ENGINE_VERSION} ===")

    raw = load_or_download()
    price = clean_ohlc(raw)

    if price.empty:
        print("No data returned for this interval/period combination.")
        print(f"Try a shorter PERIOD. Current: INTERVAL={INTERVAL}, PERIOD={PERIOD}")
        return

    print("Columns:", list(price.columns))
    print("Bars:", len(price))
    print(
        "Date range:",
        price.iloc[0].to_dict().get("Datetime", price.iloc[0].to_dict().get("Date", "N/A")),
        "->",
        price.iloc[-1].to_dict().get("Datetime", price.iloc[-1].to_dict().get("Date", "N/A")),
    )

    result = run_backtest(price)

    split_idx = int(len(result) * 0.7)
    in_sample = result.iloc[:split_idx].copy()
    out_sample = result.iloc[split_idx:].copy()

    def strat_stats(df: pd.DataFrame):
        eq = (1.0 + df["strategy_return"]).cumprod()
        total_ret = (eq.iloc[-1] - 1.0) * 100.0
        max_dd = (eq / eq.cummax() - 1.0).min() * 100.0
        ret = df["strategy_return"].fillna(0.0)
        std = ret.std()
        sharpe = (ret.mean() / std) * np.sqrt(252 * 24) if std != 0 else 0.0
        return total_ret, max_dd, sharpe

    in_ret, in_dd, in_sharpe = strat_stats(in_sample)
    out_ret, out_dd, out_sharpe = strat_stats(out_sample)

    print("\n=== WALK-FORWARD TEST ===")
    print(f"In-Sample  Return: {in_ret:.2f}% | MaxDD: {in_dd:.2f}% | Sharpe: {in_sharpe:.3f}")
    print(f"Out-Sample Return: {out_ret:.2f}% | MaxDD: {out_dd:.2f}% | Sharpe: {out_sharpe:.3f}")

    rwf = rolling_walk_forward_stats(result, n_splits=4)
    if not rwf.empty:
        print("\n=== ROLLING WALK-FORWARD TEST ===")
        print(rwf.to_string(index=False))

    print("\n=== QUICK DIAGNOSTICS ===")
    print("Position counts:\n", result["position"].value_counts(dropna=False))
    print("\nDecision counts:\n", result["decision"].value_counts(dropna=False))

    turnover = (result["position"] != result["position"].shift(1)).fillna(False).astype(int)

    print("\n=== SANITY DASHBOARD ===")
    print("Rows:", len(result))
    print("Turnover (position changes):", int(turnover.sum()))
    print("Non-zero strategy_return bars:", int((result["strategy_return"] != 0).sum()))

    buy_hold = (result["close"].iloc[-1] / result["close"].iloc[0] - 1.0) * 100.0
    strat = (result["equity_curve"].iloc[-1] - 1.0) * 100.0

    print(f"\nBuy&Hold %: {buy_hold:.2f}%")
    print(f"Strategy  %: {strat:.2f}%")

    trade_log = build_trade_log(result)

    if trade_log.empty:
        print("\nNo completed trades found.")
    else:
        print("\n=== TRADE LOG SUMMARY ===")
        print("Trades:", len(trade_log))
        print("Win rate:", round(trade_log["win"].mean() * 100, 2), "%")
        print("Avg trade %:", round(trade_log["pnl_pct"].mean(), 4), "%")
        print("Median trade %:", round(trade_log["pnl_pct"].median(), 4), "%")
        print("Best trade %:", round(trade_log["pnl_pct"].max(), 4), "%")
        print("Worst trade %:", round(trade_log["pnl_pct"].min(), 4), "%")

        print("\n=== ENTRY QUALITY CHECK ===")
        print("Avg PnL when win:", trade_log.loc[trade_log["win"] == 1, "pnl_pct"].mean())
        print("Avg PnL when loss:", trade_log.loc[trade_log["win"] == 0, "pnl_pct"].mean())

        print("\n=== TRADE DISTRIBUTION ===")
        print(trade_log["pnl_pct"].describe())

        print("\n=== LONG vs SHORT PERFORMANCE ===")
        for side in ["LONG", "SHORT"]:
            df_side = trade_log[trade_log["direction"] == side]
            if len(df_side) == 0:
                print(f"{side}: No trades")
            else:
                print(
                    f"{side}: Trades={len(df_side)} | "
                    f"WinRate={(df_side['win'].mean() * 100):.2f}% | "
                    f"Avg={(df_side['pnl_pct'].mean()):.3f}% | "
                    f"Best={(df_side['pnl_pct'].max()):.3f}% | "
                    f"Worst={(df_side['pnl_pct'].min()):.3f}%"
                )

    print_pro_metrics(result, trade_log)
    print_engine_signal(result, account_size=10_000.0)

    print("\n=== CURRENT ENGINE SETTINGS ===")
    print(f"Best operating timeframe: {INTERVAL}")

    if SAVE_CSV:
        ensure_dirs()
        out_dir = project_root() / "analysis"

        result_path = out_dir / "decision_summary_BASELINE.csv"
        result.to_csv(result_path, index=False)
        print("\nSaved:", result_path)

        if trade_log is not None and not trade_log.empty:
            trade_path = out_dir / "trade_log.csv"
            trade_log.to_csv(trade_path, index=False)
            print("Saved:", trade_path)

    if PLOT_EQUITY:
        plt.figure()
        result["equity_curve"].plot(title="Equity Curve")
        plt.show()

        if trade_log is not None and not trade_log.empty:
            plt.figure()
            trade_equity = (1 + trade_log["pnl_pct"] / 100.0).cumprod()
            trade_equity.plot(title="Trade-by-Trade Equity Curve")
            plt.show()

        import os

        log_path = project_root() / "analysis" / "daily_log.csv"

        latest = result.iloc[-1]

        log_row = pd.DataFrame([{
            "datetime": latest.get("Datetime", latest.get("datetime", "")),
            "price": latest.get("Close", latest.get("close", None)),
            "regime": latest.get("regime", ""),
            "decision": latest.get("decision", ""),
            "trend_dir": latest.get("trend_dir", ""),
            "position": latest.get("position", 0),
            "action": "WAIT / NO TRADE" if latest.get("position", 0) == 0 else "IN POSITION",
            "paper": "NO" if latest.get("position", 0) != 0 else (
                "YES" if latest.get("decision", "") == "GO" and latest.get("regime", "") == "TREND" else "NO"
            ),
        }])

        if os.path.exists(log_path):
            log_row.to_csv(log_path, mode="a", header=False, index=False)


        # Save to CSV (append or create)
        if os.path.exists(log_path):
            log_row.to_csv(log_path, mode='a', header=False, index=False)
        else:
            log_row.to_csv(log_path, index=False)

        print(f"Logged daily signal → {log_path}")


if __name__ == "__main__":
    main()