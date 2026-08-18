# backtest_paper_v2_FIXED.py
# Single-file backtest with:
# - NEXT_OPEN entries
# - GAP + intrabar SL/TP exits
# - Clean, single-source-of-truth PnL & fees (no double-charging)
# - Optional lookahead-safe signal shifting for NEXT_OPEN
#
# Assumes you already have:
#   - regime_classifier.py with classify_regimes(close_series) -> list/series of regime labels
#   - decision_gate.py with decision_gate(regime_or_state) -> dict including key "decision"
#   - risk_engine.py with get_risk_multiplier(regime, decision) -> float

import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import yfinance as yf

from regime_classifier import classify_regimes
from decision_gate import decision_gate
from risk_engine import get_risk_multiplier


# ======================
# CONFIG
# ======================

# =====================================
# v1.0 FROZEN BASELINE — DO NOT MODIFY
# =====================================
ENGINE_VERSION = "v1.0_baseline_1H"

TICKER = "BTC-USD"
INTERVAL = "1h"
PERIOD = "730d"

ATR_LEN = 14
STOP_ATR = 1.5
TP_ATR = 3.0

RISK_UNIT = 0.01
MAX_LEVERAGE = 3.0
USE_VOL_FILTER = True
USE_REGIME_FILTER = True

ENGINE_VERSION = "V1.0_baseline"

# --- DEBUG / EXPERIMENT TOGGLES ---
USE_DD_FACTOR = False
DD_THRESHOLD = -0.03
DD_SCALE = 0.5
DEBUG_PRINT_FIRST_N_EXITS = 5

USE_TREND_STRENGTH_FILTER = True
TREND_STRENGTH_MIN = 0.001

TICKER = "BTC-USD"
INTERVAL = "1h"
PERIOD = "730d"          # ~2 years

ATR_LEN = 14
STOP_ATR = 1.5
TP_ATR = 3.0

FEE_PER_TURN = 0.0005    # 0.05% per entry OR exit
RISK_UNIT = 0.01
MAX_LEVERAGE = 3.0
MIN_ATR_PCT = 0.001

USE_VOL_FILTER = True
VOL_FILTER_LOOKBACK = 50

USE_REGIME_FILTER = True
ALLOWED_REGIME = "TREND"

USE_TREND_CONFIRM = True
FAST_MA = 20
SLOW_MA = 50
CONFIRM_MA = 20

ENTRY_MODEL = "NEXT_OPEN"     # "NEXT_OPEN" or "CLOSE"
CONSERVATIVE_IF_BOTH_HIT = True

SAVE_CSV = True
PLOT_EQUITY = True

# IMPORTANT: lookahead safety for NEXT_OPEN.
# If True, signals used to arm the trade are shifted by 1 bar,
# so we never use the same bar's close-derived info to trade its next open incorrectly.
SHIFT_SIGNALS_FOR_NEXT_OPEN = True

# Debug
DEBUG_PRINT_FIRST_N_TRADES = 5


# ======================
# PATHS
# ======================
def project_root() -> Path:
    return Path(__file__).resolve().parents[0]

def ensure_dirs():
    (project_root() / "data").mkdir(exist_ok=True)
    (project_root() / "analysis").mkdir(exist_ok=True)


# ======================
# DATA
# ======================
def load_or_download(ticker: str = TICKER, interval: str = INTERVAL, period: str = PERIOD) -> pd.DataFrame:
    ensure_dirs()
    data_file = project_root() / "data" / f"{ticker.replace('-','')}_{interval}_{period}_yahoo.csv"

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

    df = df.reset_index(drop=True)
    return df

def clean_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    needed = ["Open", "High", "Low", "Close"]
    for c in needed:
        if c not in df.columns and c.lower() in df.columns:
            df[c] = df[c.lower()]
    for c in needed:
        if c not in df.columns:
            raise ValueError(f"Missing column '{c}'. Found: {list(df.columns)}")

    out = df.copy()
    for c in needed:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    out = out.dropna(subset=needed).reset_index(drop=True)
    return out


# ======================
# INDICATORS
# ======================
def compute_atr(price: pd.DataFrame, length: int = ATR_LEN) -> pd.Series:
    high = price["High"]
    low = price["Low"]
    close = price["Close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(length).mean()
    return atr


# ======================
# TRADE LOG
# ======================
def build_trade_log(result: pd.DataFrame) -> pd.DataFrame:
    df = result.copy()
    if "position" not in df.columns or "strategy_return" not in df.columns:
        raise ValueError("result must include 'position' and 'strategy_return'")

    pos = df["position"].astype(float)
    pos_prev = pos.shift(1).fillna(0)

    entry = (pos_prev == 0) & (pos != 0)
    exit_ = (pos_prev != 0) & (pos == 0)
    flip = (pos_prev != 0) & (pos != 0) & (pos_prev != pos)

    trades = []
    trade_id = 0
    in_trade = False
    cur = {}

    for i in range(len(df)):
        if entry.iloc[i]:
            trade_id += 1
            in_trade = True
            cur = {
                "trade_id": trade_id,
                "entry_idx": i,
                "direction": "LONG" if pos.iloc[i] == 1 else "SHORT",
            }
            continue

        if flip.iloc[i] and in_trade:
            cur["exit_idx"] = i
            trades.append(cur)
            trade_id += 1
            cur = {
                "trade_id": trade_id,
                "entry_idx": i,
                "direction": "LONG" if pos.iloc[i] == 1 else "SHORT",
            }
            continue

        if exit_.iloc[i] and in_trade:
            cur["exit_idx"] = i
            trades.append(cur)
            in_trade = False
            cur = {}

    if not trades:
        return pd.DataFrame()

    tdf = pd.DataFrame(trades)
    pnl_sum, bars_held = [], []

    for _, row in tdf.iterrows():
        a = int(row["entry_idx"])
        b = int(row["exit_idx"])
        seg = df.iloc[a:b + 1]
        pnl_sum.append(float(seg["strategy_return"].sum()))
        bars_held.append(int(len(seg)))

    tdf["bars_held"] = bars_held
    tdf["pnl_sum"] = pnl_sum
    tdf["pnl_pct"] = tdf["pnl_sum"] * 100.0
    tdf["win"] = tdf["pnl_sum"] > 0
    return tdf


def print_latest_signal(result: pd.DataFrame):
    last = result.iloc[-1]
    print("\n=== LATEST SIGNAL ===")
    print("close:", float(last["close"]))
    print("regime:", last.get("regime"))
    print("decision:", last.get("decision"))
    print("trend_dir:", int(last.get("trend_dir", 0)))
    print("position:", float(last.get("position", 0)))

    if float(last.get("position", 0)) == 1.0:
        print("ACTION: IN LONG (HOLD LONG)")
    elif float(last.get("position", 0)) == -1.0:
        print("ACTION: IN SHORT (HOLD SHORT)")
    else:
        if str(last.get("decision")) == "GO":
            if int(last.get("trend_dir", 0)) == 1:
                print("ACTION: GO LONG (ARM ENTRY)")
            elif int(last.get("trend_dir", 0)) == -1:
                print("ACTION: GO SHORT (ARM ENTRY)")
            else:
                print("ACTION: GO but direction unclear (stay flat)")
        else:
            print("ACTION: WAIT/FAKE (stay flat)")


    account_size = 10000
    risk_dollars = account_size * RISK_UNIT

    print("\n=== PAPER TRADE INSTRUCTIONS ===")

    position = float(result["position"].iloc[-1])

    if position == 1:
        print("Signal: LONG")
        print(f"Risk: ${risk_dollars:.2f}")
    elif position == -1:
        print("Signal: SHORT")
        print(f"Risk: ${risk_dollars:.2f}")
    else:
        print("Signal: FLAT (no position)")


def print_pro_metrics(result: pd.DataFrame, trade_log: pd.DataFrame):
    ret = result["strategy_return"].fillna(0.0)
    mean_ret = ret.mean()
    std_ret = ret.std()
    sharpe = (mean_ret / std_ret) * np.sqrt(252 * 24) if std_ret != 0 else 0.0

    max_dd = result["dd"].min() if "dd" in result.columns else np.nan
    exposure = (result["position"].abs() > 0).mean() if "position" in result.columns else np.nan

    print("\n=== PRO METRICS ===")
    print(f"Sharpe (annualized): {sharpe:.3f}")
    print(f"Max Drawdown: {max_dd*100:.2f}%")
    print(f"Exposure: {exposure*100:.1f}%")

    if trade_log is None or trade_log.empty:
        print("Trades: 0")
        print("⚠ No completed trades — trade metrics unavailable.")
        return

    pnl = trade_log["pnl_pct"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    win_rate = (pnl > 0).mean()
    avg_win = wins.mean() if len(wins) else np.nan
    avg_loss = losses.mean() if len(losses) else np.nan

    gross_win = wins.sum()
    gross_loss = losses.sum()  # negative
    profit_factor = (gross_win / abs(gross_loss)) if gross_loss != 0 else np.nan
    expectancy = pnl.mean()

    print(f"Trades: {len(pnl)}")
    print(f"Win rate: {win_rate*100:.1f}%")
    print(f"Avg win: {avg_win:.3f}%")
    print(f"Avg loss: {avg_loss:.3f}%")
    print(f"Profit factor: {profit_factor:.3f}")
    print(f"Expectancy/trade: {expectancy:.3f}%")

    if len(pnl) < 50:
        print("⚠ Warning: trades < 50, metrics are not statistically reliable yet.")


# ======================
# BACKTEST SIM
# ======================
def run_backtest(price: pd.DataFrame) -> pd.DataFrame:

    result = price.copy()

    close = result["Close"].astype(float)
    high = result["High"].astype(float)
    low = result["Low"].astype(float)
    open_ = result["Open"].astype(float)

    # Trend direction
    fast = close.rolling(FAST_MA).mean()
    slow = close.rolling(SLOW_MA).mean()
    trend_dir = np.where(fast > slow, 1, -1)

    # Optional trend confirm
    ma_confirm = close.rolling(CONFIRM_MA).mean()
    trend_confirm_long = (close > ma_confirm).fillna(False)
    trend_confirm_short = (close < ma_confirm).fillna(False)

    # Regime + Decision
    regimes = classify_regimes(close)
    decisions = [decision_gate(r) for r in regimes]
    decision_df = pd.DataFrame(decisions)

    if "decision" not in decision_df.columns:
        raise ValueError(f"decision_gate must return dict with key 'decision'. Got: {list(decision_df.columns)}")

    # Base frame
    result = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "regime": regimes,
        "trend_dir": trend_dir,
    })
    result = pd.concat([result, decision_df], axis=1)

    # Risk multiplier
    result["risk_multiplier"] = [
        float(get_risk_multiplier(reg, dec))
        for reg, dec in zip(result["regime"], result["decision"])
    ]

    # ATR + returns
    atr = compute_atr(price, ATR_LEN)
    result["ATR"] = atr.values
    result["returns"] = result["close"].pct_change().fillna(0.0)

    # Volatility filter
    result["atr_pct"] = (result["ATR"] / result["close"]).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if USE_VOL_FILTER:
        base = result["atr_pct"].rolling(VOL_FILTER_LOOKBACK).mean()
        result["vol_filter"] = result["atr_pct"] > base
    else:
        result["vol_filter"] = True

    # Position sizing
    atr_pct_safe = result["atr_pct"].clip(lower=MIN_ATR_PCT)
    position_size = RISK_UNIT / atr_pct_safe
    result["position_size"] = position_size.clip(upper=MAX_LEVERAGE)

    # ----------------------
    # Lookahead-safe signals for NEXT_OPEN
    # ----------------------
    if ENTRY_MODEL == "NEXT_OPEN" and SHIFT_SIGNALS_FOR_NEXT_OPEN:
        result["decision_sig"] = result["decision"].shift(1)
        result["risk_multiplier_sig"] = result["risk_multiplier"].shift(1)
        result["trend_dir_sig"] = result["trend_dir"].shift(1)
        result["vol_filter_sig"] = result["vol_filter"].shift(1)
        result["regime_sig"] = result["regime"].shift(1)
        result["confirm_long_sig"] = trend_confirm_long.shift(1)
        result["confirm_short_sig"] = trend_confirm_short.shift(1)
    else:
        result["decision_sig"] = result["decision"]
        result["risk_multiplier_sig"] = result["risk_multiplier"]
        result["trend_dir_sig"] = result["trend_dir"]
        result["vol_filter_sig"] = result["vol_filter"]
        result["regime_sig"] = result["regime"]
        result["confirm_long_sig"] = trend_confirm_long
        result["confirm_short_sig"] = trend_confirm_short


    result["entry_price"] = np.nan
    result["stop_price"] = np.nan
    result["tp_price"] = np.nan

    # ----------------------
    # SIM STATE
    # ----------------------
    sim_pos = 0
    entry_price = np.nan
    stop_price = np.nan
    tp_price = np.nan

    pending_entry = 0  # +1 / -1 / 0
    equity = 1.0
    max_equity = 1.0

    strategy_returns = []
    position_series = []

    debug_trade_count = 0

    for i in range(len(result)):
        o = float(result["open"].iloc[i])
        h = float(result["high"].iloc[i])
        l = float(result["low"].iloc[i])
        c = float(result["close"].iloc[i])

        atr_i = float(result["ATR"].iloc[i]) if not pd.isna(result["ATR"].iloc[i]) else np.nan

        # Warmup / missing ATR
        if pd.isna(atr_i) or i == 0:
            strategy_returns.append(0.0)
            position_series.append(float(sim_pos))
            continue

        prev_close = float(result["close"].iloc[i - 1])

        decision = str(result["decision_sig"].iloc[i])
        td = int(result["trend_dir_sig"].iloc[i]) if not pd.isna(result["trend_dir_sig"].iloc[i]) else 0
        rm = float(result["risk_multiplier_sig"].iloc[i]) if not pd.isna(result["risk_multiplier_sig"].iloc[i]) else 0.0
        size = float(result["position_size"].iloc[i])

        trend_strength = abs(fast.iloc[i] - slow.iloc[i]) / close.iloc[i]

        if USE_TREND_STRENGTH_FILTER:
            trend_strength_ok = trend_strength > TREND_STRENGTH_MIN
        else:
            trend_strength_ok = True

        # Filters
        if USE_REGIME_FILTER:
            regime_ok = (str(result["regime_sig"].iloc[i]) == str(ALLOWED_REGIME))
        else:
            regime_ok = True

        if USE_TREND_CONFIRM:
            if td == 1:
                trend_ok = bool(result["confirm_long_sig"].iloc[i])
            elif td == -1:
                trend_ok = bool(result["confirm_short_sig"].iloc[i])
            else:
                trend_ok = False
        else:
            trend_ok = True

        vol_ok = bool(result["vol_filter_sig"].iloc[i]) if "vol_filter_sig" in result.columns else True

        trade_allowed = (
                (decision == "GO") and
                (rm >= 0.999) and
                bool(regime_ok) and
                bool(trend_ok) and
                bool(vol_ok) and
                (td == -1 ) and
                (trend_strength_ok)
        )

        bar_ret = 0.0

        # 1) Execute pending entry at this bar's open
        entered_this_bar = False
        if sim_pos == 0 and pending_entry != 0:
            sim_pos = int(pending_entry)
            entry_price = o if ENTRY_MODEL == "NEXT_OPEN" else c
            stop_price = entry_price - STOP_ATR * atr_i if sim_pos == 1 else entry_price + STOP_ATR * atr_i
            tp_price = entry_price + TP_ATR * atr_i if sim_pos == 1 else entry_price - TP_ATR * atr_i

            result.loc[i, "entry_price"] = entry_price
            result.loc[i, "stop_price"] = stop_price
            result.loc[i, "tp_price"] = tp_price

            bar_ret -= FEE_PER_TURN  # entry fee
            pending_entry = 0
            entered_this_bar = True

        # Use correct base for returns
        base_price = entry_price if (sim_pos != 0 and entered_this_bar) else prev_close

        # 2) Exits: GAP at open first, then intrabar high/low
        exited = False
        exit_price = None

        if sim_pos != 0:

            result.loc[i, "entry_price"] = entry_price
            result.loc[i, "stop_price"] = stop_price
            result.loc[i, "tp_price"] = tp_price

            # GAP OPEN exit
            if sim_pos == 1:
                if o <= stop_price:
                    exited = True
                    exit_price = o
                elif o >= tp_price:
                    exited = True
                    exit_price = o
            elif sim_pos == -1:
                if o >= stop_price:
                    exited = True
                    exit_price = o
                elif o <= tp_price:
                    exited = True
                    exit_price = o

            # Intrabar exit if no gap exit
            if not exited:
                if sim_pos == 1:
                    stop_hit = (l <= stop_price)
                    tp_hit = (h >= tp_price)
                    if stop_hit and tp_hit:
                        exit_price = float(stop_price) if CONSERVATIVE_IF_BOTH_HIT else float(tp_price)
                        exited = True
                    elif stop_hit:
                        exit_price = float(stop_price)
                        exited = True
                    elif tp_hit:
                        exit_price = float(tp_price)
                        exited = True

                elif sim_pos == -1:
                    stop_hit = (h >= stop_price)
                    tp_hit = (l <= tp_price)
                    if stop_hit and tp_hit:
                        exit_price = float(stop_price) if CONSERVATIVE_IF_BOTH_HIT else float(tp_price)
                        exited = True
                    elif stop_hit:
                        exit_price = float(stop_price)
                        exited = True
                    elif tp_hit:
                        exit_price = float(tp_price)
                        exited = True

        # 3) If exited: realize base -> exit, pay ONE exit fee, flatten
        if sim_pos != 0 and exited:
            move = (float(exit_price) / float(base_price)) - 1.0
            bar_ret += sim_pos * float(size) * move * float(rm)
            bar_ret -= FEE_PER_TURN  # exit fee ONCE

            if debug_trade_count < DEBUG_PRINT_FIRST_N_TRADES:
                print(f"[EXIT] i={i} pos={sim_pos} base={base_price:.2f} exit={float(exit_price):.2f} ret={bar_ret:.6f}")
                debug_trade_count += 1

            sim_pos = 0
            entry_price = np.nan
            stop_price = np.nan
            tp_price = np.nan

        # 4) If still holding: earn base -> close (dd overlay here)

        elif sim_pos != 0:
            move = (c / prev_close) - 1.0

            dd_factor = 1.0
            if USE_DD_FACTOR:
                dd_i = equity / max_equity - 1.0
                if dd_i < DD_THRESHOLD:
                    dd_factor = DD_SCALE

            bar_ret += sim_pos * (size * dd_factor) * move * float(rm)

        # 5) If flat: arm new entry
        if sim_pos == 0 and pending_entry == 0 and trade_allowed:
            if ENTRY_MODEL == "NEXT_OPEN":
                pending_entry = td
                if debug_trade_count < DEBUG_PRINT_FIRST_N_TRADES:
                    print(f"[ARM ] i={i} td={td} decision={decision} rm={rm} regime_ok={regime_ok} trend_ok={trend_ok} vol_ok={vol_ok}")
            else:
                # CLOSE entry model: enter immediately at close
                sim_pos = td
                entry_price = c
                stop_price = entry_price - STOP_ATR * atr_i if sim_pos == 1 else entry_price + STOP_ATR * atr_i
                tp_price = entry_price + TP_ATR * atr_i if sim_pos == 1 else entry_price - TP_ATR * atr_i
                bar_ret -= FEE_PER_TURN

        # Update equity
        equity *= (1.0 + bar_ret)
        max_equity = max(max_equity, equity)

        strategy_returns.append(bar_ret)
        position_series.append(float(sim_pos))

    result["position"] = position_series
    result["strategy_return"] = strategy_returns
    result["equity_curve"] = (1.0 + result["strategy_return"]).cumprod()
    result["dd"] = result["equity_curve"] / result["equity_curve"].cummax() - 1.0

    print("equity_curve start:", result["equity_curve"].iloc[0])
    print("equity_curve end:", result["equity_curve"].iloc[-1])
    print("strategy %:", (result["equity_curve"].iloc[-1] - 1.0) * 100)

    return result

# ======================
# MAIN
# ======================

print(f"n=== Running {ENGINE_VERSION} ===")

def main():
    raw = load_or_download()
    price = clean_ohlc(raw)

    print("Columns:", list(price.columns))
    print("Bars:", len(price))
    print(
        "Date range:",
        price.iloc[0].to_dict().get("Datetime", price.iloc[0].to_dict().get("Date", "N/A")),
        "->",
        price.iloc[-1].to_dict().get("Datetime", price.iloc[-1].to_dict().get("Date", "N/A")),
    )

    result = run_backtest(price)

    # Walk-forward split
    split_idx = int(len(result) * 0.7)
    in_sample = result.iloc[:split_idx].copy()
    out_sample = result.iloc[split_idx:].copy()

    def strat_stats(df: pd.DataFrame):
        eq = (1.0 + df["strategy_return"]).cumprod()
        total_ret = eq.iloc[-1] - 1.0
        dd = (eq / eq.cummax() - 1.0).min()
        return total_ret * 100.0, dd * 100.0

    in_ret, in_dd = strat_stats(in_sample)
    out_ret, out_dd = strat_stats(out_sample)

    print("\n=== WALK FORWARD TEST ===")
    print(f"In-Sample  Return: {in_ret:.2f}% | MaxDD: {in_dd:.2f}%")
    print(f"Out-Sample Return: {out_ret:.2f}% | MaxDD: {out_dd:.2f}%")

    # Quick diagnostics
    print("\n=== QUICK DIAGNOSTICS ===")
    print("Position counts:\n", result["position"].value_counts(dropna=False))
    print("\nDecision counts:\n", result["decision"].value_counts(dropna=False))

    in_trade = result["position"] != 0
    print("\nAvg strategy_return when in trade:",
          float(result.loc[in_trade, "strategy_return"].mean()) if in_trade.any() else 0.0)

    turnover = (result["position"] != result["position"].shift(1)).fillna(False).astype(int)

    print("\n=== SANITY DASHBOARD ===")
    print("Rows:", len(result))
    print("Turnover (position changes):", int(turnover.sum()))
    print("Non-zero strategy_return bars:", int((result["strategy_return"] != 0).sum()))

    buy_hold = (result["close"].iloc[-1] / result["close"].iloc[0] - 1.0) * 100.0
    strat = (result["equity_curve"].iloc[-1] - 1.0) * 100.0
    print(f"\nBuy&Hold %: {buy_hold:.2f}%")
    print(f"Strategy  %: {strat:.2f}%")

    # Trade log + metrics
    trade_log = build_trade_log(result)
    if trade_log.empty:
        print("\nNo completed trades found in this window.")
    else:
        print("\n=== TRADE LOG SUMMARY ===")
        print("Trades:", len(trade_log))
        print("Win rate:", round(trade_log["win"].mean() * 100, 2), "%")
        print("Avg trade %:", round(trade_log["pnl_pct"].mean(), 4), "%")
        print("Median trade %:", round(trade_log["pnl_pct"].median(), 4), "%")
        print("Best trade %:", round(trade_log["pnl_pct"].max(), 4), "%")
        print("Worst trade %:", round(trade_log["pnl_pct"].min(), 4), "%")

        if not trade_log.empty:
            print("\n=== LONG vs SHORT PERFORMANCE ===")

            longs = trade_log[trade_log["direction"] == "LONG"]
            shorts = trade_log[trade_log["direction"] == "SHORT"]

            def summarize(name, df):
                if df.empty:
                    print(f"{name}: No trades")
                    return
                win_rate = (df["pnl_sum"] > 0).mean() * 100
                avg_trade = df["pnl_pct"].mean()
                total_return = df["pnl_sum"].sum() * 100
                print(f"{name}:")
                print(f"  Trades: {len(df)}")
                print(f"  Win rate: {win_rate:.2f}%")
                print(f"  Avg trade %: {avg_trade:.3f}%")
                print(f"  Total return % (sum of trades): {total_return:.2f}%")
                print()

            summarize("LONG", longs)
            summarize("SHORT", shorts)

    print_pro_metrics(result, trade_log)
    print_latest_signal(result)

    # Save
    if SAVE_CSV:
        ensure_dirs()
        out_dir = project_root() / "analysis"
        result_path = out_dir / "decision_summary.csv"
        result.to_csv(result_path, index=False)
        print("\nSaved:", result_path)

        if trade_log is not None and not trade_log.empty:
            trade_path = out_dir / "trade_log.csv"
            trade_log.to_csv(trade_path, index=False)
            print("Saved:", trade_path)

    # Plot
    if PLOT_EQUITY:
        result["equity_curve"].plot(title="Equity Curve")
        plt.show()


if __name__ == "__main__":
    main()