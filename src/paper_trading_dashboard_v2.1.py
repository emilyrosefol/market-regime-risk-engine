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


def format_elapsed(value: object, now_utc: pd.Timestamp) -> str:
    """Format elapsed time from a UTC timestamp without changing source data."""
    if value is None or pd.isna(value):
        return "Never"

    elapsed_seconds = max(int((now_utc - value).total_seconds()), 0)
    hours, remainder = divmod(elapsed_seconds, 3600)
    minutes = remainder // 60

    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


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

    market_files = {
        "ETC-USD": {
            "signal": analysis_dir / "paper_trade_signal_log.csv",
            "position": analysis_dir / "paper_trade_position_state.csv",
            "trades": analysis_dir / "paper_trade_trades.csv",
        },
        "BTC-USD": {
            "signal": analysis_dir / "paper_trade_signal_log_btc_usd.csv",
            "position": analysis_dir / "paper_trade_position_state_btc_usd.csv",
            "trades": analysis_dir / "paper_trade_trades_btc_usd.csv",
        },
    }

    portfolio_observations = 0
    portfolio_completed_trades = 0

    market_progress = {}

    now_utc = pd.Timestamp.now(tz="UTC")
    stale_after = pd.Timedelta(hours=2)

    for market_name, paths in market_files.items():
        market_signals = read_csv_safe(paths["signal"])
        market_trades = read_csv_safe(paths["trades"])

        missing_candles = 0

        if not market_signals.empty and "candle_time_utc" in market_signals.columns:
            candle_times = pd.to_datetime(
                market_signals["candle_time_utc"],
                errors="coerce",
                utc=True,
            ).dropna().sort_values().drop_duplicates()

            recent_cutoff = now_utc - pd.Timedelta(days=7)

            candle_times = candle_times[
                candle_times >= recent_cutoff
                ]


            if len(candle_times) >= 2:
                expected_times = pd.date_range(
                    start=candle_times.iloc[0],
                    end=candle_times.iloc[-1],
                    freq="1h",
                    tz="UTC",
                )

                missing_candles = len(expected_times.difference(candle_times))

        observations = len(market_signals)
        closed_trades = len(market_trades)

        portfolio_observations += observations
        portfolio_completed_trades += closed_trades

        latest_market_row = latest_row(market_signals)

        if latest_market_row is None:
            latest_candle = None
            is_stale = True
        else:
            latest_candle_raw = first_existing_value(
                latest_market_row,
                ["candle_time_utc", "candle_time", "timestamp", "datetime"],
                None,
            )

            latest_candle = pd.to_datetime(
                latest_candle_raw,
                errors="coerce",
                utc=True,
            )

            if pd.isna(latest_candle):
                is_stale = True
            else:
                candle_completed_at = latest_candle + pd.Timedelta(hours=1)

                is_stale = (
                        now_utc - candle_completed_at > stale_after
                )

        market_progress[market_name] = {
            "observations": observations,
            "trades": closed_trades,
            "latest_candle": latest_candle,
            "stale": is_stale,
            "missing_candles": missing_candles,
        }


    comparison_rows = []

    for market_name, paths in market_files.items():
        market_signals = read_csv_safe(paths["signal"])
        market_positions = read_csv_safe(paths["position"])

        latest = latest_row(market_signals)
        position = find_open_position(market_positions)

        if latest is None:
            comparison_rows.append(
                {
                    "Market": market_name,
                    "Price": "—",
                    "Regime": "—",
                    "Decision": "NO DATA",
                    "Edge": "—",
                    "RSI": "—",
                    "ATR %": "—",
                    "Position": "NONE",
                }
            )
            continue

        atr_pct = as_number(
            first_existing_value(latest, ["atr_pct"], None)
        )
        rsi = as_number(
            first_existing_value(latest, ["rsi"], None)
        )

        comparison_rows.append(
            {
                "Market": market_name,
                "Price": format_price(
                    first_existing_value(latest, ["close", "price"], None)
                ),
                "Regime": str(
                    first_existing_value(latest, ["regime"], "—")
                ),
                "Decision": str(
                    first_existing_value(
                        latest,
                        ["decision", "raw_decision"],
                        "—",
                    )
                ),
                "Edge": first_existing_value(
                    latest,
                    ["edge_score"],
                    "—",
                ),
                "RSI": "—" if rsi is None else f"{rsi:.1f}",
                "ATR %": "—" if atr_pct is None else f"{atr_pct * 100:.2f}%",
                "Position": (
                    "NONE"
                    if position is None
                    else str(
                        first_existing_value(
                            position,
                            ["direction", "side"],
                            "OPEN",
                        )
                    )
                ),
            }
        )

    st.markdown(
        '<div class="section-title">Market Comparison</div>',
        unsafe_allow_html=True,
    )

    st.dataframe(
        pd.DataFrame(comparison_rows),
        hide_index=True,
        use_container_width=True,
    )


    selected_market = st.selectbox(
        "Market",
        ["ETC-USD", "BTC-USD"],
        index=0,
    )

    if selected_market == "ETC-USD":
        signal_path = analysis_dir / "paper_trade_signal_log.csv"
        position_path = analysis_dir / "paper_trade_position_state.csv"
        trades_path = analysis_dir / "paper_trade_trades.csv"
    else:
        signal_path = analysis_dir / "paper_trade_signal_log_btc_usd.csv"
        position_path = analysis_dir / "paper_trade_position_state_btc_usd.csv"
        trades_path = analysis_dir / "paper_trade_trades_btc_usd.csv"

    signals = read_csv_safe(signal_path)
    positions = read_csv_safe(position_path)
    trades = read_csv_safe(trades_path)

    latest_signal = latest_row(signals)
    open_position = find_open_position(positions)
    summary = trade_summary(trades)

    # =========================
    # FORWARD-TEST HEALTH
    # =========================

    signal_observations = len(signals)
    completed_trades = len(trades)

    if positions.empty:
        open_position_count = 0
    else:
        open_position_count = 1 if open_position is not None else 0

    if all(
            progress["observations"] == 0
            for progress in market_progress.values()
    ):
        health_status = "NO DATA"

    elif any(
            progress["stale"]
            for progress in market_progress.values()
    ):
        health_status = "STALE"

    else:
        health_status = "HEALTHY"


    if latest_signal is None:
        market = selected_market
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

    # =========================
    # FORWARD-TEST HEALTH PANEL
    # =========================

    st.markdown(
        '<div class="section-title">Forward-Test Health</div>',
        unsafe_allow_html=True,
    )

    health_cols = st.columns(6)

    with health_cols[0]:
        metric_card("System Health", health_status, "Forward-test status")

    with health_cols[1]:
        metric_card("Signal Observations", signal_observations, "Completed candles logged")

    with health_cols[2]:
        metric_card("Completed Trades", completed_trades, "Closed paper trades")

    with health_cols[3]:
        metric_card("Open Positions", open_position_count, "Currently active")

    with health_cols[4]:
        etc_feed_status = (
            "STALE"
            if market_progress["ETC-USD"]["stale"]
            else "CURRENT"
        )

        metric_card(
            "ETC Feed",
            etc_feed_status,
            "Hourly data status",
        )

    with health_cols[5]:
        btc_feed_status = (
            "STALE"
            if market_progress["BTC-USD"]["stale"]
            else "CURRENT"
        )

        metric_card(
            "BTC Feed",
            btc_feed_status,
            "Hourly data status",
        )

    gap_cols = st.columns(2)

    with gap_cols[0]:
        metric_card(
            "ETC Gaps",
            market_progress["ETC-USD"]["missing_candles"],
            "Missing hourly candles - last 7 days",
        )

    with gap_cols[1]:
        metric_card(
            "BTC Gaps",
            market_progress["BTC-USD"]["missing_candles"],
            "Missing hourly candles",
        )

    # =========================
    # ENGINE RUN INTEGRITY
    # =========================

    st.markdown(
        '<div class="section-title">Engine Run Integrity</div>',
        unsafe_allow_html=True,
    )

    engine_run_log = read_csv_safe(analysis_dir / "paper_engine_run_log.csv")
    required_run_columns = {
        "started_at_utc",
        "finished_at_utc",
        "market",
        "status",
        "new_signal_rows",
    }

    if not engine_run_log.empty and required_run_columns.issubset(engine_run_log.columns):
        engine_run_log = engine_run_log.copy()
        engine_run_log["started_at_utc"] = pd.to_datetime(
            engine_run_log["started_at_utc"],
            errors="coerce",
            utc=True,
        )
        engine_run_log["finished_at_utc"] = pd.to_datetime(
            engine_run_log["finished_at_utc"],
            errors="coerce",
            utc=True,
        )
        engine_run_log["market"] = engine_run_log["market"].astype(str)
        engine_run_log["status"] = engine_run_log["status"].astype(str).str.upper()
        engine_run_log["new_signal_rows"] = pd.to_numeric(
            engine_run_log["new_signal_rows"],
            errors="coerce",
        ).fillna(0)
    else:
        engine_run_log = pd.DataFrame()

    run_cutoff = now_utc - pd.Timedelta(hours=24)
    recent_success_cutoff = now_utc - pd.Timedelta(hours=2)
    integrity_by_market = {}

    for market_name in ["ETC-USD", "BTC-USD"]:
        if engine_run_log.empty:
            market_runs = pd.DataFrame()
        else:
            market_runs = (
                engine_run_log[engine_run_log["market"] == market_name]
                .dropna(subset=["finished_at_utc"])
                .sort_values("finished_at_utc")
            )

        latest_run = market_runs.tail(1)
        successful_runs = market_runs[market_runs["status"] == "SUCCESS"] if not market_runs.empty else market_runs
        latest_success = successful_runs["finished_at_utc"].max() if not successful_runs.empty else pd.NaT
        runs_24h = market_runs[market_runs["finished_at_utc"] >= run_cutoff] if not market_runs.empty else market_runs
        errors_24h = runs_24h[runs_24h["status"] == "ERROR"] if not runs_24h.empty else runs_24h
        successes_24h = runs_24h[runs_24h["status"] == "SUCCESS"] if not runs_24h.empty else runs_24h
        latest_error_24h = errors_24h["finished_at_utc"].max() if not errors_24h.empty else pd.NaT

        latest_run_time = latest_run["finished_at_utc"].iloc[0] if not latest_run.empty else pd.NaT
        latest_status = latest_run["status"].iloc[0] if not latest_run.empty else "NO DATA"
        has_recent_success = pd.notna(latest_success) and latest_success >= recent_success_cutoff
        recovered_from_errors = (
            errors_24h.empty
            or (pd.notna(latest_success) and latest_success > latest_error_24h)
        )

        integrity_by_market[market_name] = {
            "latest_run_time": latest_run_time,
            "latest_status": latest_status,
            "latest_success": latest_success,
            "has_recent_success": has_recent_success,
            "runs_24h": len(runs_24h),
            "successes_24h": len(successes_24h),
            "errors_24h": len(errors_24h),
            "new_signal_rows_24h": int(runs_24h["new_signal_rows"].sum()) if not runs_24h.empty else 0,
            "recovered_from_errors": recovered_from_errors,
        }

    all_recent_and_successful = all(
        metrics["has_recent_success"] and metrics["latest_status"] == "SUCCESS"
        for metrics in integrity_by_market.values()
    )
    has_recent_errors = any(
        metrics["errors_24h"] > 0
        for metrics in integrity_by_market.values()
    )
    all_recovered = all(
        metrics["recovered_from_errors"]
        for metrics in integrity_by_market.values()
    )

    if not all_recent_and_successful:
        integrity_status = "ERROR"
    elif has_recent_errors and all_recovered:
        integrity_status = "WARNING"
    else:
        integrity_status = "HEALTHY"

    metric_card(
        "Overall Integrity",
        integrity_status,
        "ETC-USD + BTC-USD engine execution health",
    )

    if engine_run_log.empty:
        st.info("No engine-run integrity data is available yet.")

    for market_name, metrics in integrity_by_market.items():
        st.markdown(f"#### {market_name}")
        integrity_cols = st.columns(4)
        latest_run_display = None if pd.isna(metrics["latest_run_time"]) else metrics["latest_run_time"]
        latest_success_display = None if pd.isna(metrics["latest_success"]) else metrics["latest_success"]
        integrity_cols[0].metric("Latest Run", format_timestamp(latest_run_display))
        integrity_cols[1].metric("Latest Status", metrics["latest_status"])
        integrity_cols[2].metric("Latest Successful Run", format_timestamp(latest_success_display))
        integrity_cols[3].metric(
            "Since Latest Success",
            format_elapsed(metrics["latest_success"], now_utc),
        )

        recent_cols = st.columns(4)
        recent_cols[0].metric("Runs — 24h", metrics["runs_24h"])
        recent_cols[1].metric("Successful Runs — 24h", metrics["successes_24h"])
        recent_cols[2].metric("Errors — 24h", metrics["errors_24h"])
        recent_cols[3].metric("New Signal Rows — 24h", metrics["new_signal_rows_24h"])




    # =========================
    # DECISION & REJECTION ANALYTICS
    # =========================

    st.markdown(
        '<div class="section-title">Decision & Rejection Analytics</div>',
        unsafe_allow_html=True,
    )

    reason_rows = []

    for market_name, paths in market_files.items():
        market_signals = read_csv_safe(paths["signal"])

        if market_signals.empty or "reason" not in market_signals.columns:
            continue

        for reason_text in market_signals["reason"].fillna("").astype(str):
            reasons = [
                item.strip()
                for item in reason_text.split(",")
                if item.strip()
            ]

            for reason in reasons:
                reason_rows.append(
                    {
                        "Market": market_name,
                        "Reason": reason,
                    }
                )

    reason_df = pd.DataFrame(reason_rows)

    if reason_df.empty:
        st.info("No rejection analytics available yet.")

    else:
        reason_summary = (
            reason_df
            .groupby(["Reason", "Market"])
            .size()
            .unstack(fill_value=0)
        )

        # Make sure both market columns always exist
        for market_name in ["ETC-USD", "BTC-USD"]:
            if market_name not in reason_summary.columns:
                reason_summary[market_name] = 0

        # Observation totals used for percentages
        etc_total = max(
            market_progress["ETC-USD"]["observations"],
            1,
        )

        btc_total = max(
            market_progress["BTC-USD"]["observations"],
            1,
        )

        portfolio_total = max(
            portfolio_observations,
            1,
        )

        # Per-market percentages
        reason_summary["ETC %"] = (
                reason_summary["ETC-USD"] / etc_total * 100
        ).round(1)

        reason_summary["BTC %"] = (
                reason_summary["BTC-USD"] / btc_total * 100
        ).round(1)

        # Combined count MUST be created before Combined %
        reason_summary["Combined"] = (
                reason_summary["ETC-USD"]
                + reason_summary["BTC-USD"]
        )

        reason_summary["Combined %"] = (
                reason_summary["Combined"]
                / portfolio_total
                * 100
        ).round(1)

        # Sort biggest rejection reasons first
        reason_summary = (
            reason_summary
            .sort_values("Combined", ascending=False)
            .reset_index()
        )

        # Cleaner display names
        reason_summary = reason_summary.rename(
            columns={
                "ETC-USD": "ETC",
                "BTC-USD": "BTC",
            }
        )

        # Put columns in a clean order
        reason_summary = reason_summary[
            [
                "Reason",
                "ETC",
                "ETC %",
                "BTC",
                "BTC %",
                "Combined",
                "Combined %",
            ]
        ]

        st.dataframe(
            reason_summary,
            hide_index=True,
            use_container_width=True,
        )

    # =========================
    # REGIME BREAKDOWN
    # =========================

    st.markdown(
        '<div class="section-title">Regime Breakdown</div>',
        unsafe_allow_html=True,
    )

    regime_rows = []

    for market_name, paths in market_files.items():
        market_signals = read_csv_safe(paths["signal"])

        if market_signals.empty or "regime" not in market_signals.columns:
            continue

        regimes = (
            market_signals["regime"]
            .fillna("")
            .astype(str)
            .str.upper()
        )

        total = len(regimes)

        trend_count = int((regimes == "TREND").sum())
        range_count = int((regimes == "RANGE").sum())

        trend_pct = 0.0 if total == 0 else trend_count / total * 100
        range_pct = 0.0 if total == 0 else range_count / total * 100

        regime_rows.append(
            {
                "Market": market_name,
                "Trend": trend_count,
                "Trend %": round(trend_pct, 1),
                "Range": range_count,
                "Range %": round(range_pct, 1),
                "Observations": total,
            }
        )

    regime_df = pd.DataFrame(regime_rows)

    if regime_df.empty:
        st.info("No regime data available yet.")
    else:
        st.dataframe(
            regime_df,
            hide_index=True,
            use_container_width=True,
        )

    # =========================
    # SIGNAL CONVERSION ANALYTICS
    # =========================

    st.markdown(
        '<div class="section-title">Signal Conversion Analytics</div>',
        unsafe_allow_html=True,
    )

    conversion_rows = []

    for market_name, paths in market_files.items():
        market_signals = read_csv_safe(paths["signal"])
        market_trades = read_csv_safe(paths["trades"])

        if market_signals.empty:
            continue

        total_checks = len(market_signals)

        raw = (
            market_signals["raw_decision"]
            .fillna("")
            .astype(str)
            .str.upper()
            if "raw_decision" in market_signals.columns
            else pd.Series(dtype=str)
        )

        status = (
            market_signals["status"]
            .fillna("")
            .astype(str)
            .str.upper()
            if "status" in market_signals.columns
            else pd.Series(dtype=str)
        )

        raw_signals = int(
            (~raw.isin(["", "WAIT", "NONE", "NAN"])).sum()
        ) if not raw.empty else 0

        qualifying_signals = int(
            (status == "QUALIFYING_SIGNAL").sum()
        ) if not status.empty else 0

        opened_trades = len(market_trades)

        raw_signal_rate = (
            0.0
            if total_checks == 0
            else raw_signals / total_checks * 100
        )

        qualification_rate = (
            0.0
            if raw_signals == 0
            else qualifying_signals / raw_signals * 100
        )

        trade_open_rate = (
            0.0
            if qualifying_signals == 0
            else opened_trades / qualifying_signals * 100
        )

        conversion_rows.append(
            {
                "Market": market_name,
                "Candle Checks": total_checks,
                "Raw Signals": raw_signals,
                "Raw Signal %": round(raw_signal_rate, 1),
                "Qualifying Signals": qualifying_signals,
                "Qualification %": round(qualification_rate, 1),
                "Completed Trades": opened_trades,
                "Completed Trade %": round(trade_open_rate, 1),
            }
        )

    conversion_df = pd.DataFrame(conversion_rows)

    if conversion_df.empty:
        st.info("No signal conversion data available yet.")
    else:
        st.dataframe(
            conversion_df,
            hide_index=True,
            use_container_width=True,
        )



    # =========================
    # FORWARD-TEST PROGRESS
    # =========================

    st.markdown(
        '<div class="section-title">Forward-Test Progress</div>',
        unsafe_allow_html=True,
    )

    progress_target = 100
    trade_progress = min(portfolio_completed_trades / progress_target, 1.0)


    progress_cols = st.columns(4)

    with progress_cols[0]:
        metric_card(
            "ETC Observations",
            market_progress["ETC-USD"]["observations"],
            f'{market_progress["ETC-USD"]["trades"]} completed trades',
        )

    with progress_cols[1]:
        metric_card(
            "BTC Observations",
            market_progress["BTC-USD"]["observations"],
            f'{market_progress["BTC-USD"]["trades"]} completed trades',
        )

    with progress_cols[2]:
        metric_card(
            "Portfolio Trades",
            portfolio_completed_trades,
            f"Target: {progress_target}+ completed trades",
        )

    with progress_cols[3]:
        progress_status = (
            "VALIDATION READY"
            if portfolio_completed_trades >= progress_target
            else "COLLECTING DATA"
        )

        metric_card(
            "Validation Stage",
            progress_status,
            "ETC + BTC combined",
        )


    st.progress(trade_progress)

    st.caption(
        f"{portfolio_completed_trades} / {progress_target} completed paper trades "
        f"across ETC + BTC | {portfolio_observations} total forward observations."
    )


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

    # =========================
    # TRADE QUALITY ANALYTICS
    # =========================

    st.markdown(
        '<div class="section-title">Trade Quality Analytics</div>',
        unsafe_allow_html=True,
    )

    trade_quality_rows = []

    for market_name, paths in market_files.items():
        market_trades = read_csv_safe(paths["trades"])

        if market_trades.empty:
            trade_quality_rows.append(
                {
                    "Market": market_name,
                    "Completed Trades": 0,
                    "Wins": 0,
                    "Losses": 0,
                    "Win Rate %": 0.0,
                    "Average R": 0.0,
                    "Best R": 0.0,
                    "Worst R": 0.0,
                    "Total R": 0.0,
                }
            )
            continue

        r_col = next(
            (
                name
                for name in [
                "r_multiple",
                "result_r",
                "realized_r",
            ]
                if name in market_trades.columns
            ),
            None,
        )

        if r_col is None:
            trade_quality_rows.append(
                {
                    "Market": market_name,
                    "Completed Trades": len(market_trades),
                    "Wins": 0,
                    "Losses": 0,
                    "Win Rate %": 0.0,
                    "Average R": 0.0,
                    "Best R": 0.0,
                    "Worst R": 0.0,
                    "Total R": 0.0,
                }
            )
            continue

        r_values = pd.to_numeric(
            market_trades[r_col],
            errors="coerce",
        ).dropna()

        if r_values.empty:
            wins = 0
            losses = 0
            win_rate = 0.0
            average_r = 0.0
            best_r = 0.0
            worst_r = 0.0
            total_r = 0.0

        else:
            wins = int((r_values > 0).sum())
            losses = int((r_values < 0).sum())

            win_rate = (
                    wins / len(r_values) * 100
            )

            average_r = float(r_values.mean())
            best_r = float(r_values.max())
            worst_r = float(r_values.min())
            total_r = float(r_values.sum())

        trade_quality_rows.append(
            {
                "Market": market_name,
                "Completed Trades": len(r_values),
                "Wins": wins,
                "Losses": losses,
                "Win Rate %": round(win_rate, 1),
                "Average R": round(average_r, 2),
                "Best R": round(best_r, 2),
                "Worst R": round(worst_r, 2),
                "Total R": round(total_r, 2),
            }
        )

    trade_quality_df = pd.DataFrame(trade_quality_rows)

    if portfolio_completed_trades == 0:
        st.info(
            "Trade-quality statistics will populate automatically "
            "after the first paper trade closes."
        )

    st.dataframe(
        trade_quality_df,
        hide_index=True,
        use_container_width=True,
    )




    # --- Forward Test Monitor ---
    st.markdown(
        '<div class="section-title">Forward Test Monitor</div>',
        unsafe_allow_html=True,
    )

    if signals.empty:
        st.info("Monitoring statistics will appear after signal checks are recorded.")
    else:
        total_checks = len(signals)

        if "raw_decision" in signals.columns:
            raw = signals["raw_decision"].fillna("").astype(str).str.upper()
            raw_signals = int((~raw.isin(["", "WAIT", "NONE", "NAN"])).sum())
        else:
            raw_signals = 0

        if "status" in signals.columns:
            status = signals["status"].fillna("").astype(str).str.upper()
            qualifying = int(
                (~status.isin(["", "NO_TRADE", "NONE", "NAN"])).sum()
            )
        else:
            qualifying = 0

        no_trades = total_checks - qualifying

        monitor_cols = st.columns(4)
        monitor_cols[0].metric("Candle Checks", total_checks)
        monitor_cols[1].metric("Raw Signals", raw_signals)
        monitor_cols[2].metric("Qualifying Trades", qualifying)
        monitor_cols[3].metric("No-Trade Checks", no_trades)

        if "reason" in signals.columns:
            reasons = (
                signals["reason"]
                .dropna()
                .astype(str)
                .replace("", "No reason recorded")
                .value_counts()
                .rename_axis("Rejection Reason")
                .reset_index(name="Count")
            )

            if not reasons.empty:
                st.markdown("##### Most Common Outcomes / Rejection Reasons")
                st.dataframe(
                    reasons,
                    hide_index=True,
                    use_container_width=True,
                )
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
        # Keep only valid V3 signal-log rows
        if "regime" in display_signals.columns:
            display_signals = display_signals[
                display_signals["regime"].astype(str).str.upper().isin(["TREND", "RANGE"])
            ]
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
