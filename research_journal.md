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