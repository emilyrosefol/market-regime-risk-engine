# Market Regime Risk Engine — Forward-Test Research Journal

## Entry Date
YYYY-MM-DD

## Forward-Test Window
Start:
End:

## Data Snapshot

### ETC-USD
- Signal observations:
- Completed trades:
- TREND observations:
- RANGE observations:
- RSI rejection %:
- ATR rejection %:
- Average RSI:
- Average ATR %:
- Current ATR direction:
- Current RSI direction:

### BTC-USD
- Signal observations:
- Completed trades:
- TREND observations:
- RANGE observations:
- RSI rejection %:
- ATR rejection %:
- Average RSI:
- Average ATR %:
- Current ATR direction:
- Current RSI direction:

## Infrastructure Health

- ETC latest engine run:
- ETC run status:
- BTC latest engine run:
- BTC run status:
- ETC 7-day gaps:
- BTC 7-day gaps:
- Errors since previous journal entry:
- Recovered errors:
- Any unexplained missing data:

## What Changed in the Data?

- Regime changes:
- Volatility changes:
- RSI behavior:
- Rejection-pattern changes:
- Signal activity:
- Trade activity:

## Observations

1.
2.
3.

## Hypotheses to Test Later

Important: record ideas here but do **not** change the strategy during the active forward test.

1.
2.
3.

## Things I Am Tempted to Change

-
-
-

## Why I Am Not Changing Them Yet

- Forward-test sample is still accumulating.
- Current behavior may be regime-dependent.
- Changes during the test would contaminate the prospective sample.

## Data Quality Notes

- Duplicate rows:
- Missing candles:
- Scheduler issues:
- API/data-source issues:
- Database/import issues:

## Current Conclusion

Short summary of what the evidence currently suggests, without claiming statistical significance.

## Next Review

Date:

# Forward-Test Research Journal — Entry 001

## Entry Date
2026-09-02

## Forward-Test Window
Start: 2026-08-12
End: 2026-09-02

## Data Snapshot

### Portfolio
- Total signal observations: 529
- Completed trades: 0
- TREND observations: 510
- RANGE observations: 19
- Current sample is overwhelmingly TREND-classified.

### ETC-USD
- Signal observations: 316
- Completed trades: 0
- TREND observations: 305
- RANGE observations: 11
- RSI rejection rate: 30.1%
- ATR rejection rate: 57.9%
- Average RSI: 49.51
- Average ATR %: 1.255%
- Latest engine run: 2026-09-02 14:05 UTC
- Successful engine runs recorded: 45
- Error runs recorded: 7

### BTC-USD
- Signal observations: 213
- Completed trades: 0
- TREND observations: 205
- RANGE observations: 8
- RSI rejection rate: 43.7%
- ATR rejection rate: 4.2%
- Average RSI: 50.08
- Average ATR %: 0.601%
- Latest engine run: 2026-09-02 14:06 UTC
- Successful engine runs recorded: 32
- Error runs recorded: 8


## Infrastructure Health

- ETC latest engine run: 2026-09-02 14:05 UTC
- BTC latest engine run: 2026-09-02 14:06 UTC
- Recorded ETC successes: 45
- Recorded BTC successes: 32
- Recorded ETC errors: 7
- Recorded BTC errors: 8
- Some historical errors include environment/testing events and should not automatically be interpreted as current engine failures.
- Current gap counts: check dashboard at review time.
- Current stale-feed status: check dashboard at review time.


## What Changed in the Data?

### Regime
Both markets remain overwhelmingly classified as TREND.

ETC:
- 305 / 316 observations classified TREND
- 11 / 316 classified RANGE

BTC:
- 205 / 213 observations classified TREND
- 8 / 213 classified RANGE

There is still insufficient RANGE data for meaningful regime comparison.

### Volatility / ATR
ETC continues to show substantially greater relative volatility than BTC.

- ETC average ATR: 1.255%
- BTC average ATR: 0.601%

ETC's average ATR percentage is approximately twice BTC's in the current sample.

Earlier daily analysis showed ETC ATR rejection was highly concentrated during a high-volatility period and later declined substantially. This suggests the aggregate ATR rejection rate may be time/regime dependent rather than a permanent market characteristic.

### RSI
BTC currently encounters the RSI filter more frequently than ETC.

- BTC RSI rejection: 43.7%
- ETC RSI rejection: 30.1%

Previous filter-overlap analysis showed BTC rejection behavior was predominantly RSI-related, while ETC rejection behavior was predominantly ATR-related.


## Observations

1. ETC and BTC are producing materially different filter behavior despite using the same engine framework.

2. ETC is considerably more affected by the volatility gate:
   - ETC ATR rejection: 57.9%
   - BTC ATR rejection: 4.2%

3. BTC is more affected by the RSI filter:
   - BTC RSI rejection: 43.7%
   - ETC RSI rejection: 30.1%

4. The forward-test sample is heavily concentrated in TREND conditions. RANGE performance cannot yet be evaluated reliably.

5. No qualifying paper trade has completed yet.

6. The absence of completed trades is currently treated as data, not as evidence that thresholds should be loosened.


## Hypotheses to Test Later

1. The current ATR limits may interact very differently with high-volatility assets such as ETC than with BTC.

2. ETC's high aggregate ATR rejection rate may primarily reflect particular volatility episodes rather than a permanently unsuitable threshold.

3. BTC may require different market-specific treatment eventually if RSI continues to dominate its rejection behavior.

4. Market-specific calibration may ultimately outperform identical thresholds across all assets.

5. The strategy may generate very low signal frequency under the market conditions represented by this forward-test window.


## Things I Am Tempted to Change

- ATR limits
- RSI limits
- Entry sensitivity
- Edge threshold
- Signal-generation rules


## Why I Am Not Changing Them Yet

- The prospective forward-test sample is still accumulating.
- There are currently zero completed forward trades.
- RANGE observations are extremely limited.
- Rejection behavior has already changed substantially through time.
- Changing parameters now would contaminate the current forward test.
- Proposed changes will be recorded as hypotheses and evaluated only after sufficient evidence accumulates.


## Data Quality Notes

- SQLite research database is a separate research mirror.
- CSV files remain the live source of truth.
- SQLite importer is idempotent.
- Duplicate research-database keys previously verified at 0.
- Engine executions are being recorded in the append-only audit log.
- Historical engine errors remain visible rather than being deleted.
- No source CSVs are modified by the research database workflow.


## Current Conclusion

The forward test is functioning as a data-collection experiment, but there is not yet enough evidence to evaluate trading performance because no paper trades have completed.

The strongest current descriptive finding is that the same filter architecture behaves differently across ETC and BTC. ETC has experienced substantially more ATR-based rejection, while BTC has experienced substantially more RSI-based rejection.

The ETC ATR effect has also changed materially through time, reinforcing the decision not to tune parameters based only on aggregate rejection rates.

No strategy changes are justified at this stage.


## Next Review

Target: approximately 3–4 days from this entry, or earlier if:
- the first qualifying signal occurs,
- the first paper position opens or closes,
- an unexplained infrastructure issue appears,
- either market becomes stale for an extended period.


## Entry 002 — 2026-09-24

### Review Window
Previous review: 2026-09-02  
Current review: 2026-09-24

Strategy parameters remained frozen during this review period. No RSI, ATR,
edge-score, regime, stop-loss, take-profit, or risk parameters were changed in
response to forward-test results.

### Current Forward-Test Snapshot

Portfolio:
- Signal observations: 1,547
- Completed trades: 1
- Markets: BTC-USD, ETC-USD

BTC-USD:
- Observations: 722
- TREND: 694
- RANGE: 28
- Average RSI: 51.35
- Average ATR%: 0.533%
- RSI rejection rate: 40.0%
- ATR rejection rate: 1.8%
- Completed trades: 1

ETC-USD:
- Observations: 825
- TREND: 810
- RANGE: 15
- Average RSI: 51.45
- Average ATR%: 1.244%
- RSI rejection rate: 39.6%
- ATR rejection rate: 56.8%
- Completed trades: 0

### Change Since Entry 001

BTC observations increased from 213 to 722 (+509).

ETC observations increased from 316 to 825 (+509).

The previously observed difference between the markets remains visible:
ETC continues to experience substantially more ATR-filter rejection than BTC.

BTC and ETC now have similar average RSI values, while their average ATR%
and ATR rejection rates remain materially different.

This is descriptive evidence only. It does not justify market-specific
parameter changes at this stage.

### Regime Distribution

TREND continues to dominate the forward-test sample.

BTC:
- TREND: 694 / 722 (~96.1%)
- RANGE: 28 / 722 (~3.9%)

ETC:
- TREND: 810 / 825 (~98.2%)
- RANGE: 15 / 825 (~1.8%)

RANGE observations remain limited, particularly for ETC. Conclusions about
RANGE behavior therefore remain sample-size constrained.

### First Completed Forward-Test Trade

Market: BTC-USD
Direction: SHORT
Entry signal: GO_FAKE_SHORT
Entry regime: RANGE
Entry candle: 2026-09-13 17:00 UTC
Position opened: 2026-09-13 18:05:03 UTC

Entry price: $77,298.59
Stop price: $77,532.80
Target price: $76,830.18

Entry ATR: $234.21
Entry RSI: 53.69
Edge score: 80
Risk: $100
Simulated units: 0.42697 BTC
Bars held: 5

Exit candle: 2026-09-13 22:00 UTC
Closure processed: 2026-09-14 01:45:42 UTC
Exit reason: TAKE_PROFIT
Exit price: $76,830.18
Result: +2.0R
Paper P&L: +$200

Signal history showed WAIT decisions before the qualifying setup. At the
17:00 UTC candle, BTC was classified as RANGE and GO_FAKE_SHORT passed all
entry filters with an edge score of 80.

The regime later changed to TREND while the position was being managed.
The position ultimately reached its predefined take-profit.

This is the first completed trade and is not sufficient evidence to evaluate
strategy profitability, win rate, expectancy, or robustness.

### Engine / Infrastructure Integrity

Recorded engine runs:

BTC:
- Total runs: 166
- Successful runs: 144
- Non-success runs: 22
- New signal rows logged: 602
- Latest recorded run: 2026-09-24 01:12:14 UTC

ETC:
- Total runs: 190
- Successful runs: 164
- Non-success runs: 26
- New signal rows logged: 629
- Latest recorded run: 2026-09-24 01:17:32 UTC

During this review period, forward-test infrastructure experienced scheduler
and execution interruptions. Investigation identified issues including
user-login state and working-directory configuration.

The scheduled tasks were updated with the project directory as the Start In
directory. Manual Task Scheduler tests subsequently returned 0x0, and later
engine logs recorded successful ETC and BTC executions and catch-up behavior.

These infrastructure issues are documented separately from strategy
performance. Missed execution or delayed processing should not be interpreted
as a trading-strategy failure.

### Observations

1. TREND remains overwhelmingly dominant in both market samples.
2. RANGE observations remain relatively scarce.
3. ETC continues to be much more frequently constrained by the ATR filter.
4. BTC ATR rejection remains comparatively uncommon.
5. RSI rejection is now similar across the two markets.
6. The first completed trade originated from a BTC RANGE observation.
7. One successful trade provides essentially no statistical evidence about
   long-run strategy performance.

### Hypotheses to Continue Observing

- Market-specific volatility behavior may eventually warrant investigation,
  but current evidence does not justify parameter changes.
- ETC's higher ATR rejection may reflect persistent differences in volatility
  behavior or volatility episodes.
- BTC may continue to produce qualifying setups differently from ETC.
- Low trade frequency may be an inherent property of the frozen strategy.
- RANGE performance cannot be meaningfully assessed until substantially more
  RANGE observations and completed trades are collected.

### Things I Am Tempted to Change

- ATR limits
- RSI limits
- Edge-score threshold
- Parameters to increase trade frequency

### Why I Am Not Changing Them

The prospective forward test is designed to evaluate the frozen strategy,
not continually optimize it against newly observed data.

There is currently only one completed trade. Changing parameters now would
contaminate the forward test and make later results harder to interpret.

### Current Conclusion

The forward test is continuing to collect useful data.

The system has now demonstrated one complete prospective trade lifecycle:
market observation -> regime classification -> qualifying signal -> position
opening -> position management -> predefined exit -> trade logging -> research
database ingestion.

This confirms an important operational milestone, but does not validate the
strategy.

No strategy changes are justified at this time.

### Next Review

Continue collecting observations and completed trades under the frozen
protocol.

At the next review:
- Recheck regime distribution.
- Recheck RSI and ATR rejection behavior by market.
- Review additional completed trades individually.
- Compare cumulative R only after the trade sample grows.
- Continue monitoring scheduler and engine-run integrity.
- 