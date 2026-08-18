"""Market Regime Risk Platform — Dashboard v2.

Run from the project root:
    streamlit run src/paper_trading_dashboard_v2.py

This dashboard is read-only. It reads CSV files created by
paper_trader_v3_position_manager.py and never places or modifies orders.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st


APP_TITLE = "Market Regime Risk Platform"
DEFAULT_MARKET = "ETC-USD"
START_EQUITY = 10_000.0
RISK_PCT = 0.01
REFRESH_SECONDS = 30


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)


CUSTOM_CSS = """
<style>
    .stApp {
        background: linear-gradient(135deg, #080b12 0%, #111827 55%, #0b1220 100%);
        color: #eef2ff;
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stToolbar"] { right: 1rem; }
    .block-container {
        max-width: 1500px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    .hero {
        padding: 1.6rem 1.8rem;
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 20px;
        background: rgba(15, 23, 42, 0.72);
        box-shadow: 0 18px 55px rgba(0, 0, 0, 0.28);
        margin-bottom: 1.2rem;
    }
    .hero-title {
        font-size: 2.1rem;
        font-weight: 760;
        letter-spacing: -0.035em;
        margin: 0;
    }
    .hero-subtitle {
        color: #94a3b8;
        margin-top: .35rem;
        font-size: .98rem;
    }
    .live-pill {
        display: inline-flex;
        align-items: center;
        gap: .45rem;
        padding: .35rem .65rem;
        border-radius: 999px;
        border: 1px solid rgba(34, 197, 94, .45);
        background: rgba(34, 197, 94, .10);
        color: #86efac;
        font-size: .78rem;
        font-weight: 700;
        letter-spacing: .08em;
    }
    .dot {
        width: .48rem;
        height: .48rem;
        border-radius: 999px;
        background: #22c55e;
        box-shadow: 0 0 12px rgba(34, 197, 94, .9);
    }
    .card {
        min-height: 122px;
        padding: 1.15rem 1.25rem;
        border-radius: 18px;
        border: 1px solid rgba(148, 163, 184, 0.16);
        background: rgba(15, 23, 42, 0.68);
        box-shadow: 0 12px 36px rgba(0, 0, 0, 0.22);
    }
    .card-label {
        color: #94a3b8;
        font-size: .78rem;
        font-weight: 700;
        letter-spacing: .10em;
        text-transform: uppercase;
        margin-bottom: .55rem;
    }
    .card-value {
        font-size: 1.72rem;
        font-weight: 760;
        letter-spacing: -0.03em;
        color: #f8fafc;
    }
    .card-note {
        color: #64748b;
        font-size: .78rem;
        margin-top: .35rem;
    }
    .section-title {
        margin: 1.6rem 0 .75rem 0;
        font-size: 1.2rem;
        font-weight: 740;
        letter-spacing: -.02em;
    }
    .status-box {
        padding: 1.2rem 1.3rem;
        border-radius: 18px;
        border: 1px solid rgba(148, 163, 184, 0.16);
        background: rgba(15, 23, 42, 0.68);
        min-height: 235px;
    }
    .status-empty {
        display: flex;
        flex-direction: column;
        justify-content: center;
        min-height: 155px;
        color: #94a3b8;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 16px;
        overflow: hidden;
    }
    div[data-testid="stMetric"] {
        background: rgba(15, 23, 42, 0.66);
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 16px;
        padding: .9rem 1rem;
    }
    div[data-testid="stMetricLabel"] { color: #94a3b8; }
    .footer-note {
        color: #64748b;
        font-size: .78rem;
        text-align: center;
        margin-top: 2rem;
    }
</style>
"""


@st.cache_data(ttl=REFRESH_SECONDS)
def read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
        return pd.DataFrame()


def first_existing_value(row: pd.Series, names: list[str], default: object = None) -> object:
    for name in names:
        if name in row.index and pd.notna(row[name]):
            return row[name]
    return default


def as_number(value: object) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def format_price(value: object) -> str:
    number = as_number(value)
    return "—" if number is None else f"${number:,.4f}"


def format_r(value: object) -> str:
    number = as_number(value)
    return "—" if number is None else f"{number:+.2f}R"


def format_timestamp(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return "—" if value is None else str(value)
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def latest_row(df: pd.DataFrame) -> Optional[pd.Series]:
    return None if df.empty else df.iloc[-1]


def find_open_position(positions: pd.DataFrame) -> Optional[pd.Series]:
    if positions.empty:
        return None
    status_col = next(
        (name for name in ["status", "position_status", "trade_status"] if name in positions.columns),
        None,
    )
    if status_col is None:
        return positions.iloc[-1]
    open_rows = positions[
        positions[status_col].astype(str).str.upper().isin(["OPEN", "ACTIVE"])
    ]
    return None if open_rows.empty else open_rows.iloc[-1]


def trade_summary(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty:
        return {
            "count": 0,
            "win_rate": 0.0,
            "total_r": 0.0,
            "average_r": 0.0,
            "profit_factor": 0.0,
            "equity": START_EQUITY,
        }

    r_col = next(
        (name for name in ["r_multiple", "result_r", "realized_r"] if name in trades.columns),
        None,
    )
    if r_col is None:
        return {
            "count": len(trades),
            "win_rate": 0.0,
            "total_r": 0.0,
            "average_r": 0.0,
            "profit_factor": 0.0,
            "equity": START_EQUITY,
        }

    values = pd.to_numeric(trades[r_col], errors="coerce").dropna()
    if values.empty:
        return {
            "count": len(trades),
            "win_rate": 0.0,
            "total_r": 0.0,
            "average_r": 0.0,
            "profit_factor": 0.0,
            "equity": START_EQUITY,
        }

    wins = values[values > 0].sum()
    losses = abs(values[values < 0].sum())
    profit_factor = float(wins / losses) if losses > 0 else (float("inf") if wins > 0 else 0.0)

    equity = START_EQUITY
    for r_value in values:
        equity += equity * RISK_PCT * float(r_value)

    return {
        "count": int(len(values)),
        "win_rate": float((values > 0).mean() * 100),
        "total_r": float(values.sum()),
        "average_r": float(values.mean()),
        "profit_factor": profit_factor,
        "equity": float(equity),
    }


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="card">
            <div class="card-label">{label}</div>
            <div class="card-value">{value}</div>
            <div class="card-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_equity_series(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    r_col = next(
        (name for name in ["r_multiple", "result_r", "realized_r"] if name in trades.columns),
        None,
    )
    if r_col is None:
        return pd.DataFrame()
    r_values = pd.to_numeric(trades[r_col], errors="coerce").dropna()
    if r_values.empty:
        return pd.DataFrame()

    equity = START_EQUITY
    running_max = START_EQUITY
    rows = [{"trade": 0, "equity": equity, "drawdown_pct": 0.0}]
    for trade_number, r_value in enumerate(r_values, start=1):
        equity += equity * RISK_PCT * float(r_value)
        running_max = max(running_max, equity)
        rows.append(
            {
                "trade": trade_number,
                "equity": equity,
                "drawdown_pct": (equity / running_max - 1.0) * 100,
            }
        )
    return pd.DataFrame(rows).set_index("trade")


def main() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    project_root = Path(__file__).resolve().parent
    analysis_dir = project_root / "analysis"
    signal_path = analysis_dir / "paper_trade_signal_log_BAD_BACKUP.csv"
    position_path = analysis_dir / "paper_trade_position_state.csv"
    trades_path = analysis_dir / "paper_trade_trades.csv"

    signals = read_csv_safe(signal_path)
    positions = read_csv_safe(position_path)
    trades = read_csv_safe(trades_path)

    latest_signal = latest_row(signals)
    open_position = find_open_position(positions)
    summary = trade_summary(trades)

    if latest_signal is None:
        market = DEFAULT_MARKET
        regime = "—"
        decision = "NO DATA"
        edge_score = "—"
        latest_close = "—"
        latest_time = "—"
        reason = "Run the paper position manager to create live signal data."
    else:
        market = str(first_existing_value(latest_signal, ["market", "ticker"], DEFAULT_MARKET))
        regime = str(first_existing_value(latest_signal, ["regime", "market_regime"], "—"))
        decision = str(
            first_existing_value(latest_signal, ["final_decision", "decision", "raw_decision"], "—")
        )
        edge_number = as_number(first_existing_value(latest_signal, ["edge_score", "score"], None))
        edge_score = "—" if edge_number is None else f"{edge_number:.0f}"
        latest_close = format_price(first_existing_value(latest_signal, ["close", "price"], None))
        latest_time = format_timestamp(
            first_existing_value(
                latest_signal,
                ["candle_time_utc", "candle_time", "timestamp", "datetime"],
                None,
            )
        )
        reason = str(first_existing_value(latest_signal, ["reason", "filter_reason"], ""))

    header_left, header_right = st.columns([4, 1])
    with header_left:
        st.markdown(
            f"""
            <div class="hero">
                <div class="hero-title">{APP_TITLE}</div>
                <div class="hero-subtitle">Live paper-trading intelligence, position state, and risk analytics.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with header_right:
        st.markdown(
            """
            <div style="padding-top: 1.55rem; text-align: right;">
                <span class="live-pill"><span class="dot"></span> PAPER LIVE</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.button("Refresh data", use_container_width=False):
        st.cache_data.clear()
        st.rerun()

    top_cols = st.columns(6)
    with top_cols[0]:
        metric_card("Market", market, "Hourly feed")
    with top_cols[1]:
        metric_card("Price", latest_close, "Latest completed candle")
    with top_cols[2]:
        metric_card("Regime", regime, "Current classification")
    with top_cols[3]:
        metric_card("Decision", decision, reason[:42])
    with top_cols[4]:
        metric_card("Edge Score", edge_score, "Minimum entry score: 75")
    with top_cols[5]:
        metric_card("Last Candle", latest_time, "UTC")

    st.markdown('<div class="section-title">Position & Account</div>', unsafe_allow_html=True)
    left, right = st.columns([1.15, 1])

    with left:
        st.markdown('<div class="status-box">', unsafe_allow_html=True)
        st.markdown("#### Open Paper Position")
        if open_position is None:
            st.markdown(
                """
                <div class="status-empty">
                    <div style="font-size:1.35rem;font-weight:700;color:#e2e8f0;">No open position</div>
                    <div style="margin-top:.35rem;">The engine is monitoring completed hourly candles for a qualifying setup.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            direction = str(first_existing_value(open_position, ["direction", "side"], "—"))
            status = str(first_existing_value(open_position, ["status", "position_status"], "OPEN"))
            entry = first_existing_value(open_position, ["entry_price", "entry"], None)
            stop = first_existing_value(open_position, ["stop_price", "stop"], None)
            target = first_existing_value(open_position, ["target_price", "tp_price", "target"], None)
            current_r = first_existing_value(open_position, ["unrealized_r", "current_r", "r_multiple"], None)
            opened = first_existing_value(open_position, ["open_time", "entry_time", "opened_at"], None)

            position_metrics = st.columns(3)
            position_metrics[0].metric("Direction", direction)
            position_metrics[1].metric("Status", status)
            position_metrics[2].metric("Current P/L", format_r(current_r))
            details = pd.DataFrame(
                {
                    "Field": ["Entry", "Stop", "Target", "Opened"],
                    "Value": [format_price(entry), format_price(stop), format_price(target), format_timestamp(opened)],
                }
            )
            st.dataframe(details, hide_index=True, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="status-box">', unsafe_allow_html=True)
        st.markdown("#### Paper Account")
        account_cols = st.columns(6)
        account_cols[0].metric("Simulated Equity", f"${summary['equity']:,.2f}")
        account_cols[1].metric("Closed Trades", int(summary["count"]))
        account_cols[2].metric("Win Rate", f"{summary['win_rate']:.1f}%")
        account_cols[3].metric("Total R", f"{summary['total_r']:+.2f}R")
        account_cols[4].metric("Average R", f"{summary['average_r']:+.2f}R")
        pf_text = "∞" if summary["profit_factor"] == float("inf") else f"{summary['profit_factor']:.2f}"
        account_cols[5].metric("Profit Factor", pf_text)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-title">Performance</div>', unsafe_allow_html=True)
    equity_series = build_equity_series(trades)
    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.markdown("#### Paper Equity Curve")
        if equity_series.empty:
            st.info("The equity curve will appear after the first paper trade closes.")
        else:
            st.line_chart(equity_series[["equity"]], use_container_width=True)
    with chart_right:
        st.markdown("#### Paper Drawdown")
        if equity_series.empty:
            st.info("Drawdown analytics will appear after the first paper trade closes.")
        else:
            st.line_chart(equity_series[["drawdown_pct"]], use_container_width=True)

    st.markdown('<div class="section-title">Recent Signal Checks</div>', unsafe_allow_html=True)
    if signals.empty:
        st.warning("No signal data found. Run paper_trader_v3_position_manager.py first.")
    else:
        display_signals = signals.tail(20).iloc[::-1].copy()
        preferred = [
            "candle_time",
            "market",
            "close",
            "regime",
            "raw_decision",
            "final_decision",
            "edge_score",
            "rsi",
            "atr",
            "status",
            "reason",
        ]
        columns = [column for column in preferred if column in display_signals.columns]
        if columns:
            display_signals = display_signals[columns]
        st.dataframe(display_signals, hide_index=True, use_container_width=True, height=420)

    st.markdown('<div class="section-title">Closed Paper Trades</div>', unsafe_allow_html=True)
    if trades.empty:
        st.info("No closed paper trades yet. Trade history will populate automatically.")
    else:
        st.dataframe(trades.tail(20).iloc[::-1], hide_index=True, use_container_width=True)

    with st.expander("System details"):
        st.code(
            "\n".join(
                [
                    f"Signal log:    {signal_path}",
                    f"Position:      {position_path}",
                    f"Trade history: {trades_path}",
                    "Real orders:    disabled",
                    f"Cache refresh: {REFRESH_SECONDS} seconds",
                ]
            )
        )

    st.markdown(
        '<div class="footer-note">Research and paper-trading interface only. No brokerage connection or real order execution.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
