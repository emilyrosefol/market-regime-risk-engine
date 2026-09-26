# Market Regime & Risk Engine

An explainable, risk-first trading research platform designed to classify
market conditions, evaluate rule-based trade setups, manage simulated
positions, and measure strategy behaviour through automated forward testing.

The project is currently running in paper-trading mode using completed
hourly market candles.

---

## Problem

Many trading strategies apply the same entry and risk rules regardless of
market conditions.

A strategy that behaves well in a trending market may perform poorly in a
range, while changes in volatility can significantly alter the risk of an
otherwise similar setup.

This project explores a different approach:

**classify the environment first, then decide whether risk should be taken.**

---

## System Architecture

```text
Market Data
    ↓
Completed Candle Validation
    ↓
Feature Engineering
    ↓
Market Regime Classification
    ↓
Rule-Based Signal Generation
    ↓
Signal Qualification & Risk Filters
    ↓
Position Manager
    ↓
Paper Trade Execution
    ↓
CSV Source-of-Truth Logs
    ↓
├── Streamlit Monitoring Dashboard
├── Engine Run Audit Log
└── SQLite Research Database
        ↓
    SQL Research & Forward-Test Analysis

---

## Current Features

### Market Regime Classification
- Classifies current market conditions
- Separates market context from trade execution
- Allows strategy behaviour to depend on regime

### Signal Engine
- Generates rule-based candidate setups
- Uses technical and volatility information
- Can reject setups that fail predefined requirements

### Risk & Position Management
- Determines whether a signal qualifies for execution
- Tracks simulated open positions
- Applies predefined stop-loss and profit-target logic
- Keeps execution separate from signal generation

### Automated Paper Trading
- Evaluates completed hourly candles
- Runs without placing real-money orders
- Records both trades and rejected opportunities
- Maintains persistent signal and position logs

### Forward-Test Monitoring
The dashboard tracks:

- Candle checks
- Raw signals
- Qualifying trades
- No-trade decisions
- Rejection reasons
- Simulated equity
- Win rate
- Total R
- Average R
- Profit factor
- Drawdown

This makes it possible to evaluate not only strategy performance, but also
why the system chooses not to trade.

---

## Research & Validation

### Prospective Forward Testing

The current strategy is being evaluated through automated paper forward testing
on ETC-USD and BTC-USD using completed hourly candles.

A documented forward-test protocol freezes the active strategy configuration,
including signal rules, filters, risk parameters, and execution behaviour.

During the active collection period:

- Strategy parameters are not changed in response to individual outcomes.
- Low trade frequency is treated as an observation, not a reason to relax filters.
- Infrastructure or data issues are separated from strategy changes.
- Original signal and engine-run history is preserved.
- Proposed improvements are documented for future experiments rather than
  immediately applied to the active strategy.

The goal is to accumulate prospective evidence while reducing the risk of
overfitting the strategy to observations it has already seen.

### Research Data Layer

Operational CSV logs remain the live source of truth for the paper-trading engine.

A separate SQLite research database provides a read-only analytical layer for:

- Signal and regime analysis
- Filter rejection analysis
- Engine-run integrity
- Completed trade analysis
- Cross-market comparison
- SQL-based research queries

The research database does not feed decisions back into the trading engine.

See `FORWARD_TEST_PROTOCOL.md` for the complete experimental protocol and
`research_journal.md` for documented observations and hypotheses.

## Design Philosophy

- Risk first
- Explainability over unnecessary complexity
- Systems over isolated signals
- Separate signal generation from execution
- Measure rejected opportunities as well as executed trades
- Validate with forward data before changing strategy parameters

---

## Current Testing Stage

The engine is currently undergoing automated prospective paper forward testing
on ETC-USD and BTC-USD.

The active strategy configuration is frozen while new market observations
accumulate. The purpose of this stage is to evaluate:

- Infrastructure reliability and data continuity
- Regime distribution across markets
- Raw and qualifying signal frequency
- Filter rejection behaviour
- Completed paper-trade outcomes
- Differences in strategy behaviour across assets and market conditions

The forward-test sample is still developing, particularly for completed trades
and RANGE-regime observations. Performance conclusions are therefore intentionally
deferred until substantially more evidence has accumulated.

No real capital is being deployed.

---

## Technology

- **Python** — core engine, position management, data processing, and automation
- **pandas** — market-data transformation and research analysis
- **SQLite / SQL** — analytical research database and reusable research queries
- **Streamlit** — forward-test monitoring and analytics dashboard
- **yfinance** — hourly OHLC market-data retrieval
- **CSV persistence** — operational signal, position, trade, and engine-run logs
- **Windows Task Scheduler** — automated hourly paper-engine execution
- **Git / GitHub** — version control, research history, and project documentation


---

## Project Structure

```text
market-regime-risk-engine/
│
├── src/
│   ├── paper_trader_v3_position_manager.py
│   │   └── Paper-trading engine and position management
│   │
│   ├── paper_trading_dashboard_v2.1.py
│   │   └── Streamlit forward-test monitoring dashboard
│   │
│   ├── build_research_db.py
│   │   └── Builds the SQLite analytical research database
│   │
│   └── analysis/
│       └── Operational paper-trading logs and research data
│
├── sql/
│   └── research_examples.sql
│       └── Reusable SQL research queries
│
├── FORWARD_TEST_PROTOCOL.md
│   └── Frozen strategy configuration and experimental protocol
│
├── research_journal.md
│   └── Forward-test observations, hypotheses, and review history
│
└── README.md
    └── Project overview and documentation
```


## Limitations

This project is an active research system and should not be interpreted as a validated trading strategy.

Current limitations include:

- The prospective forward-test sample is still developing.
- Completed trade count is currently too small for reliable performance conclusions.
- RANGE-regime observations remain relatively limited.
- Market data is sourced through yfinance and may be subject to availability or timing issues.
- Paper execution does not reproduce all real-world effects such as slippage, liquidity constraints, fees, or order-book dynamics.
- Current research focuses on a small number of cryptocurrency markets.
- Strategy parameters remain frozen during the active forward-test period.

Results from the paper-trading environment are research observations, not evidence of future profitability.
---

## Roadmap

### Current — Forward-Test Validation

- Continue automated ETC-USD and BTC-USD paper forward testing
- Accumulate a larger sample of completed trades
- Monitor data continuity and engine-run reliability
- Analyze regime frequency and filter behaviour across markets
- Document observations without modifying the frozen strategy

### Next — Research & Evaluation

- Evaluate trade expectancy and R-multiple distribution once sample size is sufficient
- Compare strategy behaviour across different market regimes
- Expand SQL-based research and diagnostic analysis
- Improve reproducibility of research reports and experiments
- Investigate potential strategy improvements as separate experiments

### Later — Platform Expansion

- Add additional asset classes and markets
- Develop richer portfolio-level risk analytics
- Explore market-specific calibration only when supported by forward-test evidence
- Build a more complete decision-intelligence layer around regime, risk, and confidence
- Evaluate live execution only after research, infrastructure, and risk-control requirements are met

---

## Status

**Active development — prospective paper forward testing**

- ETC-USD and BTC-USD monitored on completed hourly candles
- Automated paper-trading engine active
- Strategy configuration frozen under the documented forward-test protocol
- Real-money order execution disabled
- Signal, trade, and engine-run history preserved for research
- SQLite and SQL research layer active
- Streamlit monitoring and analytics dashboard active

The current priority is evidence collection, infrastructure reliability, and disciplined analysis rather than strategy optimization.