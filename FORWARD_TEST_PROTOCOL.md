# Forward-Test Protocol

## Purpose and prospective freeze

This document records the ETC-USD + BTC-USD forward test as a frozen prospective
paper-trading experiment. The purpose is to measure infrastructure reliability,
signal/filter behavior, regime coverage, and paper outcomes under future market
conditions without adapting the strategy to its observed results.

Protocol recorded: **2026-09-02**. Settings were read directly from
`src/paper_trader_v3_position_manager.py`.
Engine source SHA-256:
`B6E7E7B4298824DBC9D89E608A3A883102BA429794710ED8F9C9E20A1C0EE44A`.

This snapshot governs continuing collection. It does not establish that this
exact revision was preregistered or unchanged before today. Earlier observations
retain their actual provenance and any known software-change history.

## Scope and forward-test start

- Markets: **ETC-USD and BTC-USD**.
- Interval: **1 hour** (`INTERVAL = "1h"`).
- Engine version: `paper_trader_v3_position_manager`.
- Market selection: `TICKER = os.getenv("PAPER_MARKET", "ETC-USD")`.
  ETC is the default; BTC uses `PAPER_MARKET=BTC-USD`.
- **Real orders are disabled.** There is no brokerage connection.

Observed collection starts, from the retained signal CSVs:

| Market | Earliest check, UTC | Earliest logged candle, UTC |
| --- | --- | --- |
| ETC-USD | 2026-08-12 20:55:54 | 2026-08-12 19:00:00 |
| BTC-USD | 2026-08-24 16:57:03 | 2026-08-24 15:00:00 |

The earliest observed forward-test start is **2026-08-12**. Two-market collection
has evidence from **2026-08-24** onward. These are minima of `checked_at_utc`
and `candle_time_utc`, not an assumed deployment date or proof of an earlier
formal protocol. Candle time is distinct from execution/check time, especially
for catch-up observations. No fixed collection end date is established here.

## Exact configuration snapshot

| Engine setting | Value |
| --- | --- |
| `ENGINE_VERSION` | `"paper_trader_v3_position_manager"` |
| `INTERVAL` | `"1h"` |
| `PERIOD` | `"60d"` |
| `ATR_LEN` | `14` |
| `FAST_MA` | `20` |
| `SLOW_MA` | `50` |
| `RANGE_LOOKBACK` | `20` |
| `BUFFER` | `0.001` |
| `STOP_ATR` | `1.0` |
| `TP_ATR` | `2.0` |
| `MIN_EDGE_SCORE` | `75` |
| `MIN_ATR_PCT` | `0.001` |
| `MAX_ATR_PCT` | `0.01` |
| `START_EQUITY` | `10_000.0` |
| `RISK_PCT` | `0.01` |
| `CONSERVATIVE_IF_BOTH_HIT` | `True` |
| `DEBUG` | `False` |
| `LOG_WAIT_DECISIONS` | `True` |

### Indicators and regime thresholds

- MA20 and MA50 are rolling arithmetic means of Close over 20 and 50 candles.
  Trend direction is 1 for MA20 > MA50, -1 for MA20 < MA50, otherwise 0.
- True range is the maximum of High - Low, abs(High - previous Close), and
  abs(Low - previous Close). ATR is its 14-candle rolling arithmetic mean.
  `atr_pct = atr / Close`.
- RSI uses 14-candle rolling arithmetic means of gains and losses, with zero
  average loss replaced by NaN before calculating
  `100 - 100 / (1 + average_gain / average_loss)`. It is not Wilder smoothing.
- Range high/low are the rolling 20-candle maximum High/minimum Low, shifted
  one candle. MA gap is abs(MA20 - MA50) / Close.
- RANGE requires all of: ATR/Close below its rolling 50-candle mean,
  MA gap < **0.003**, and **45 <= RSI <= 55** (inclusive).
  Otherwise the classification is TREND.

### Raw signals and qualification

All raw candidate conditions below require RANGE.

| Raw decision | Conditions |
| --- | --- |
| `GO_FAKE_LONG` | Low < prior range low; Close > prior range low; RSI < 50 |
| `GO_FAKE_SHORT` | High > prior range high; Close < prior range high; RSI > 50 |
| `GO_RANGE_LONG` | Decision still WAIT; Close <= prior range low * (1 + 0.001); RSI < 50 |
| `GO_RANGE_SHORT` | Decision still WAIT; Close >= prior range high * (1 - 0.001); RSI > 50 |

Fake assignments precede range assignments. Long decisions map to signal 1;
short decisions to -1; WAIT to 0.

A qualifying entry requires a nonzero signal, raw decision **GO_FAKE_LONG or
GO_FAKE_SHORT only**, **30 <= RSI <= 60**, **0.001 <= ATR/Close <= 0.01**
(0.1% to 1.0%, inclusive), and **edge score >= 75**.
Range-long/range-short candidates can be logged but are not allowed entries.
ATR, ATR %, RSI, MA20, MA50, range high, and range low must be non-missing;
missing required values raise a runtime error.

A qualifying record retains its raw decision, has LONG/SHORT direction, and
status QUALIFYING_SIGNAL. Otherwise final decision is WAIT, direction NONE,
and status NO_TRADE. Reasons accumulate as applicable: no signal; signal type
not allowed; RSI outside 30-60; ATR percentage outside limits; edge score below
75. A passing record says "All entry filters passed."

### Exact edge scoring

A zero signal is recorded with score 0; nonzero signals use this additive score:

| Component | Condition | Points |
| --- | --- | --- |
| Direction base | signal == 1 | 30 |
| Direction base | otherwise (short for scored nonzero signals) | 10 |
| (High - Low) / Close | <= 0.005 | +30 |
| (High - Low) / Close | > 0.005 and <= 0.010 | +20 |
| (High - Low) / Close | > 0.010 | +5 |
| abs(Close - MA20) / Close | 0.002 through 0.010, inclusive | +25 |
| abs(Close - MA20) / Close | < 0.002 | +15 |
| abs(Close - MA20) / Close | > 0.010 | +10 |
| Trend direction | nonzero | +15 |

The score function substitutes 0.0 for either ratio when Close is zero.
The discrete score is not a calibrated probability.

## Exact risk and paper-execution behavior

- Entry price is the qualifying candle's Close.
- Long stop/target: entry - 1.0 * entry ATR / entry + 2.0 * entry ATR.
- Short stop/target: entry + 1.0 * entry ATR / entry - 2.0 * entry ATR.
- Risk dollars = `START_EQUITY * RISK_PCT = 10_000.0 * 0.01 = 100.0`.
  This is fixed-base per-position risk, not compounding from realized equity.
- Risk per unit = abs(entry - stop). Units = 100.0 / risk per unit, or 0.0
  if risk per unit is not positive.
- At most one open position is managed per market's state file. There is no
  shared ETC/BTC portfolio risk cap implemented in this engine.
- Only the newest completed candle can open a new position; catch-up signal
  rows do not create retroactive entries.
- Existing positions process available completed candles after their last
  checked candle. A cycle starting with an existing position does not open a
  replacement position that same cycle, even if the position closes.
- Long stops/targets use Low <= stop / High >= target; short stops/targets
  use High >= stop / Low <= target.
- If both stop and target are touched, the stop wins because
  `CONSERVATIVE_IF_BOTH_HIT=True`.
- Exit price is the configured stop/target. Stop outcomes are -1.0R; target
  outcomes are `TP_ATR / STOP_ATR = 2.0R`.
  P/L dollars = stored risk dollars * realized R.
- Unrealized R uses the original stop distance.
- No fee/slippage deduction, trailing stop, or time-based exit is implemented.
  Paper outcomes are not evidence of actual execution performance.

## Data sources and live CSV files

OHLC data comes from Yahoo Finance through `yfinance.download`, with the
selected market, `interval="1h"`, `period="60d"`, `auto_adjust=False`,
`progress=False`, and `threads=False`.

Timestamps are parsed as UTC. Invalid required OHLC/timestamp rows are removed;
rows are sorted and duplicate timestamps retain the last row. Only candles
whose timestamp + one hour <= current UTC time are eligible. The 60-day
download supports indicators and catch-up, not 60 days of prospective trades.

Paths below are relative to the repository root. The engine's
`project_root()` helper actually returns its containing `src` directory.

| Market | Signal log | Position state | Closed trades |
| --- | --- | --- | --- |
| ETC-USD | `src/analysis/paper_trade_signal_log.csv` | `src/analysis/paper_trade_position_state.csv` | `src/analysis/paper_trade_trades.csv` |
| BTC-USD | `src/analysis/paper_trade_signal_log_btc_usd.csv` | `src/analysis/paper_trade_position_state_btc_usd.csv` | `src/analysis/paper_trade_trades_btc_usd.csv` |

Signal deduplication uses market + candle time. With no last logged candle,
only the latest candle is considered for logging; otherwise available candles
newer than the last logged candle are considered. WAIT observations are logged
because `LOG_WAIT_DECISIONS=True`.

Trade histories are appended on closure. Position CSVs are operational
snapshots, not append-only history: the existing engine updates an open state
and removes that state file when no position remains. This documentation does
not change that behavior or authorize manual log rewriting.

**The CSVs remain the live source of truth.**
`src/analysis/market_research.db` is analytics-only, populated separately by
`src/build_research_db.py`. It does not replace CSVs or feed research decisions
back into the engine. The dashboard remains a read-only analytics consumer.

## Engine audit logging

Shared append-only audit file: `src/analysis/paper_engine_run_log.csv`.

Full schema:

```text
started_at_utc, finished_at_utc, market, interval, engine_version, status,
rows_before, rows_after, new_signal_rows, candle_before, candle_after, error
```

The wrapper records SUCCESS after a normal cycle and ERROR on failure before
re-raising. Existing runtime-error conversion to SystemExit(1) is retained;
the underlying cause is recorded when available.
`new_signal_rows = max(rows_after - rows_before, 0)`.

Zero new rows is not proof of a duplicate candle or a failed run. Inspect
status, timestamps, errors, and the underlying CSVs together. Snapshot read
failures currently fall back to zero rows and an empty candle value, so those
cases require investigation instead of treating the count as authoritative.
Audit coverage started later than signal collection; absent earlier audit rows
do not prove an engine run did not occur.

## Active collection window and change control

1. Strategy parameters, signal rules, thresholds, risk settings, sizing, and
   intended execution behavior cannot change during the active collection
   window except to fix a verified software or data bug.
2. **No parameter tuning should be performed merely because trade frequency is
   low.** Low frequency is an experimental result, not permission to relax
   filters, lower the edge threshold, or change market/interval selection.
3. Bug fixes must be documented separately with evidence, affected dates and
   markets, source revisions, before/after behavior, verification, and impact
   on comparability. They must restore intended strategy behavior, not change
   it under the label of a bug fix.
4. Preserve original observations and audit history. Document affected records
   or periods rather than silently rewriting/deleting logs. Report pre-fix and
   post-fix segments separately when comparability is uncertain.
5. Proposed improvements and exploratory findings go into
   `research_journal.md`, not the live strategy. This protocol references that
   journal without creating or modifying it.
6. An intended strategy change belongs to a separately versioned future
   experiment with its own prospective baseline, not this collection window.
7. This document changes no scheduler configuration, code, CSV schema,
   dashboard calculation, or database. Collection does not automatically stop
   or change at a reporting milestone. No fixed ending date is invented here.

## Evaluation targets

- **Infrastructure reliability:** observed versus expected runs, success/error
  rates, recent successful runs, recovery, candle gaps, and catch-up latency.
  Signal rows are not a proxy for execution counts.
- **Signal frequency:** raw signals, qualifying signals, and completed trades,
  with denominators and observation durations per market.
- **Regime coverage:** RANGE/TREND counts, proportions, and time coverage by
  market; disclose sparse or absent groups.
- **Rejection behavior:** frequency and combinations of filter reasons. Reasons
  can overlap, so their counts need not sum to the observation count.
- **Completed paper trades:** sample size, wins/losses, duration, and exit
  reasons, distinct from raw/qualifying signal counts.
- **Expectancy in R when sufficient trades exist:** mean realized R over
  completed trades, with sample size and uncertainty. Do not infer reliable
  expectancy from unclosed positions or sparse samples.
- **Drawdown:** realized paper P/L/equity drawdown, distinguished from
  mark-to-market drawdown and hypothetical compounded analytics curves.
  Engine sizing remains fixed-base.
- **Market/regime attribution:** ETC/BTC and entry-regime outcomes, with unequal
  samples, shared market exposure, and empty groups explicitly reported.

**100 completed trades is a research target, not automatic proof of validity.**
It does not establish independence, sufficient regime coverage, robust positive
expectancy, real-world execution quality, or readiness for real orders. Review
uncertainty, sample composition, drawdown, infrastructure incidents, and model
limitations. The milestone must not trigger automatic tuning or live trading.

Distinguish exploratory findings from prospective evaluation. Any future
evaluation-window or stopping-rule declaration must be documented transparently,
not used to selectively discard inconvenient observations.
