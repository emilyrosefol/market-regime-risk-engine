-- Market Regime Risk Engine: beginner-friendly research queries
-- Run after: .\.venv\Scripts\python.exe src\build_research_db.py


    -- ============================================================
-- CURRENT VS ENTRY 001 BASELINE COMPARISON
-- Compares the latest research database snapshot to Journal Entry 001.
-- ============================================================



WITH baseline AS (
    SELECT
        'BTC-USD' AS market,
        213 AS baseline_observations,
        205 AS baseline_trend,
        8 AS baseline_range,
        43.7 AS baseline_rsi_rejection_pct,
        4.2 AS baseline_atr_rejection_pct,
        50.08 AS baseline_avg_rsi,
        0.601 AS baseline_avg_atr_pct,
        0 AS baseline_completed_trades

    UNION ALL

    SELECT
        'ETC-USD',
        316,
        305,
        11,
        30.1,
        57.9,
        49.51,
        1.255,
        0
),

current_stats AS (
    SELECT
        market,
        COUNT(*) AS observations,

        SUM(
            CASE
                WHEN regime = 'TREND'
                THEN 1 ELSE 0
            END
        ) AS trend_observations,

        SUM(
            CASE
                WHEN regime = 'RANGE'
                THEN 1 ELSE 0
            END
        ) AS range_observations,

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
        ) AS atr_rejection_pct,

        ROUND(AVG(rsi), 2) AS avg_rsi,

        ROUND(
            AVG(atr_pct) * 100,
            3
        ) AS avg_atr_pct

    FROM signal_checks
    GROUP BY market
),

trade_stats AS (
    SELECT
        market,
        COUNT(*) AS completed_trades
    FROM trades
    GROUP BY market
)

SELECT
    c.market,

    c.observations,
    c.observations - b.baseline_observations
        AS observation_change,

    c.trend_observations,
    c.trend_observations - b.baseline_trend
        AS trend_change,

    c.range_observations,
    c.range_observations - b.baseline_range
        AS range_change,

    c.rsi_rejection_pct,
    ROUND(
        c.rsi_rejection_pct
        - b.baseline_rsi_rejection_pct,
        1
    ) AS rsi_rejection_change,

    c.atr_rejection_pct,
    ROUND(
        c.atr_rejection_pct
        - b.baseline_atr_rejection_pct,
        1
    ) AS atr_rejection_change,

    c.avg_rsi,
    ROUND(
        c.avg_rsi - b.baseline_avg_rsi,
        2
    ) AS avg_rsi_change,

    c.avg_atr_pct,
    ROUND(
        c.avg_atr_pct - b.baseline_avg_atr_pct,
        3
    ) AS avg_atr_change,

    COALESCE(t.completed_trades, 0)
        AS completed_trades,

    COALESCE(t.completed_trades, 0)
        - b.baseline_completed_trades
        AS completed_trade_change

FROM current_stats c

JOIN baseline b
    ON c.market = b.market

LEFT JOIN trade_stats t
    ON c.market = t.market

ORDER BY c.market;
""")



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

