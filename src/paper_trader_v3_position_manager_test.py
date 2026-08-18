"""Offline test harness for paper_trader_v3_position_manager.

This script does not download live data and does not touch the live paper-trading
CSV files. It uses deterministic fake candles in a dedicated test directory to
verify that the position manager can:

1. open and persist a simulated position;
2. keep the position open when neither stop nor target is reached;
3. close the position at the take-profit target and write trade history;
4. close a separate position at the stop loss.

No real orders are possible.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

import paper_trader_v3_position_manager as manager


TEST_DIR = Path(__file__).resolve().parent / "analysis" / "position_manager_test"


def reset_test_directory() -> None:
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    TEST_DIR.mkdir(parents=True, exist_ok=True)


def test_signal_log_path() -> Path:
    return TEST_DIR / "test_signal_log.csv"


def test_position_state_path() -> Path:
    return TEST_DIR / "test_position_state.csv"


def test_trade_history_path() -> Path:
    return TEST_DIR / "test_trade_history.csv"


def install_test_paths() -> None:
    """Redirect the imported manager's file functions to isolated test files."""
    manager.signal_log_path = test_signal_log_path
    manager.position_state_path = test_position_state_path
    manager.trade_history_path = test_trade_history_path


def make_long_decision() -> dict:
    return {
        "checked_at_utc": "2026-07-22T03:00:00+00:00",
        "candle_time_utc": "2026-07-22T02:00:00+00:00",
        "engine_version": "position_manager_offline_test",
        "market": manager.TICKER,
        "interval": manager.INTERVAL,
        "close": 7.00,
        "high": 7.03,
        "low": 6.98,
        "regime": "RANGE",
        "raw_decision": "GO_FAKE_LONG",
        "decision": "GO_FAKE_LONG",
        "signal": 1,
        "direction": "LONG",
        "edge_score": 100,
        "rsi": 48.0,
        "atr": 0.10,
        "atr_pct": 0.10 / 7.00,
        "status": "QUALIFYING_SIGNAL",
        "reason": "Offline test signal.",
    }


def make_short_decision() -> dict:
    return {
        "checked_at_utc": "2026-07-22T07:00:00+00:00",
        "candle_time_utc": "2026-07-22T06:00:00+00:00",
        "engine_version": "position_manager_offline_test",
        "market": manager.TICKER,
        "interval": manager.INTERVAL,
        "close": 7.00,
        "high": 7.02,
        "low": 6.98,
        "regime": "RANGE",
        "raw_decision": "GO_FAKE_SHORT",
        "decision": "GO_FAKE_SHORT",
        "signal": -1,
        "direction": "SHORT",
        "edge_score": 80,
        "rsi": 52.0,
        "atr": 0.10,
        "atr_pct": 0.10 / 7.00,
        "status": "QUALIFYING_SIGNAL",
        "reason": "Offline test signal.",
    }


def candle_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_long_target_test() -> None:
    print("\nTEST 1 — LONG POSITION, HOLD, THEN TARGET")

    decision = make_long_decision()
    logged = manager.append_signal_log(decision)
    require(logged, "The initial test signal was not written.")

    position = manager.open_position(decision)
    manager.save_position_state(position)
    require(test_position_state_path().exists(), "Position-state CSV was not created.")

    loaded = manager.load_position_state()
    require(loaded is not None, "Saved position could not be loaded.")
    require(str(loaded["status"]) == "OPEN", "Loaded position is not OPEN.")

    hold_candles = candle_frame(
        [
            {
                "timestamp": "2026-07-22T03:00:00+00:00",
                "Open": 7.00,
                "High": 7.12,
                "Low": 6.95,
                "Close": 7.08,
            }
        ]
    )
    updated, closed, processed = manager.manage_open_position(loaded, hold_candles)
    require(processed == 1, "Expected one hold candle to be processed.")
    require(updated is not None and closed is None, "Position closed during hold test.")
    manager.save_position_state(updated)

    target_candles = candle_frame(
        [
            {
                "timestamp": "2026-07-22T04:00:00+00:00",
                "Open": 7.08,
                "High": 7.25,
                "Low": 7.04,
                "Close": 7.21,
            }
        ]
    )
    updated, closed, processed = manager.manage_open_position(updated, target_candles)
    require(processed == 1, "Expected one target candle to be processed.")
    require(updated is None and closed is not None, "Target test did not close the position.")
    require(closed["exit_reason"] == "TAKE_PROFIT", "Target exit reason is incorrect.")
    require(float(closed["r_multiple"]) == 2.0, "Target result should equal +2R.")
    manager.save_position_state(updated)

    require(not test_position_state_path().exists(), "Open-state CSV was not cleared after close.")
    require(test_trade_history_path().exists(), "Trade-history CSV was not created.")

    print("PASS: Long position persisted, remained open, and closed at +2R target.")


def run_short_stop_test() -> None:
    print("\nTEST 2 — SHORT POSITION, THEN STOP LOSS")

    decision = make_short_decision()
    position = manager.open_position(decision)
    manager.save_position_state(position)

    stop_candles = candle_frame(
        [
            {
                "timestamp": "2026-07-22T07:00:00+00:00",
                "Open": 7.00,
                "High": 7.12,
                "Low": 6.96,
                "Close": 7.09,
            }
        ]
    )
    updated, closed, processed = manager.manage_open_position(position, stop_candles)
    require(processed == 1, "Expected one stop candle to be processed.")
    require(updated is None and closed is not None, "Stop test did not close the position.")
    require(closed["exit_reason"] == "STOP_LOSS", "Stop exit reason is incorrect.")
    require(float(closed["r_multiple"]) == -1.0, "Stop result should equal -1R.")
    manager.save_position_state(updated)

    history = pd.read_csv(test_trade_history_path())
    require(len(history) == 2, "Trade history should contain two closed test trades.")

    print("PASS: Short position closed correctly at -1R stop loss.")


def print_results() -> None:
    history = pd.read_csv(test_trade_history_path())

    print("\n====================================")
    print("POSITION MANAGER OFFLINE TEST PASSED")
    print("====================================")
    print(f"Closed test trades: {len(history)}")
    print(f"First result:       {history.iloc[0]['r_multiple']:.2f}R")
    print(f"Second result:      {history.iloc[1]['r_multiple']:.2f}R")
    print(f"Test folder:        {TEST_DIR}")
    print("Live CSVs touched:  no")
    print("Real orders:        disabled")
    print("====================================")


def main() -> None:
    reset_test_directory()
    install_test_paths()
    run_long_target_test()
    run_short_stop_test()
    print_results()


if __name__ == "__main__":
    main()
