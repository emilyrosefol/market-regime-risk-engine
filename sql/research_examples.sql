-- Market Regime Risk Engine: beginner-friendly research queries
-- Run after: .\.venv\Scripts\python.exe src\build_research_db.py

-- 1. Observations per market
SELECT market, COUNT(*) AS observations
FROM signal_checks
GROUP BY market
ORDER BY market;

-- 2. Regime percentages within each market
SELECT
    market,
    regime,
    COUNT(*) AS observations,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY market), 2)
        AS regime_percentage
FROM signal_checks
GROUP BY market, regime
ORDER BY market, observations DESC;

-- 3. Rejection reasons (the complete reason text recorded by the engine)
SELECT market, reason, COUNT(*) AS occurrences
FROM signal_checks
WHERE reason IS NOT NULL AND TRIM(reason) <> ''
GROUP BY market, reason
ORDER BY occurrences DESC, market;

-- 4. Raw-signal counts, excluding WAIT/NONE/blank observations
SELECT market, raw_decision, COUNT(*) AS raw_signal_count
FROM signal_checks
WHERE UPPER(COALESCE(raw_decision, '')) NOT IN ('', 'WAIT', 'NONE', 'NAN')
GROUP BY market, raw_decision
ORDER BY market, raw_signal_count DESC;

-- 5. Engine-run success rate
SELECT
    market,
    COUNT(*) AS total_runs,
    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) AS successful_runs,
    ROUND(
        100.0 * SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0),
        2
    ) AS success_rate_pct
FROM engine_runs
GROUP BY market
ORDER BY market;

-- 6. Errors from the last 24 hours
SELECT started_at_utc, finished_at_utc, market, status, error
FROM engine_runs
WHERE status = 'ERROR'
  AND datetime(finished_at_utc) >= datetime('now', '-24 hours')
ORDER BY finished_at_utc DESC;

-- 7. Completed trades by market
SELECT market, COUNT(*) AS completed_trades
FROM trades
GROUP BY market
ORDER BY market;



-- ============================================================
-- DAILY FORWARD-TEST RESEARCH SUMMARY
-- TREND observations only; requires >= 20 observations per day.
-- Shows RSI/ATR levels, rejection rates, daily changes and direction.
-- ============================================================


WITH daily AS (
    SELECT
        market,
        DATE(candle_time_utc) AS day,
        COUNT(*) AS observations,

        ROUND(AVG(rsi), 2) AS avg_rsi,

        ROUND(
            AVG(atr_pct) * 100,
            3
        ) AS avg_atr_pct,

        ROUND(
            100.0 * SUM(
                CASE
                    WHEN reason LIKE '%RSI outside 30-60%'
                    THEN 1 ELSE 0
                END
            ) / COUNT(*),
            1
        ) AS rsi_rejection_pct,

        ROUND(
            100.0 * SUM(
                CASE
                    WHEN reason LIKE '%ATR percentage outside limits%'
                    THEN 1 ELSE 0
                END
            ) / COUNT(*),
            1
        ) AS atr_rejection_pct

    FROM signal_checks

    WHERE regime = 'TREND'

    GROUP BY
        market,
        DATE(candle_time_utc)

    HAVING COUNT(*) >= 20
),

changes AS (
    SELECT
        *,

        LAG(rsi_rejection_pct) OVER (
            PARTITION BY market
            ORDER BY day
        ) AS prev_rsi_pct,

        LAG(atr_rejection_pct) OVER (
            PARTITION BY market
            ORDER BY day
        ) AS prev_atr_pct

    FROM daily
)

SELECT
    market,
    day,
    observations,
    avg_rsi,
    avg_atr_pct,
    rsi_rejection_pct,

    ROUND(
        rsi_rejection_pct - prev_rsi_pct,
        1
    ) AS rsi_change,

    CASE
        WHEN prev_rsi_pct IS NULL THEN 'First Day'
        WHEN rsi_rejection_pct - prev_rsi_pct <= -10 THEN 'Falling'
        WHEN rsi_rejection_pct - prev_rsi_pct >= 10 THEN 'Rising'
        ELSE 'Stable'
    END AS rsi_direction,

    atr_rejection_pct,

    ROUND(
        atr_rejection_pct - prev_atr_pct,
        1
    ) AS atr_change,

    CASE
        WHEN prev_atr_pct IS NULL THEN 'First Day'
        WHEN atr_rejection_pct - prev_atr_pct <= -10 THEN 'Falling'
        WHEN atr_rejection_pct - prev_atr_pct >= 10 THEN 'Rising'
        ELSE 'Stable'
    END AS atr_direction

FROM changes

ORDER BY
    day,
    market;
""")

