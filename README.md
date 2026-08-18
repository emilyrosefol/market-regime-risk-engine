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

Market Data  
↓  
Completed Candle Validation  
↓  
Technical Indicators  
↓  
Market Regime Classification  
↓  
Rule-Based Signal Generation  
↓  
Signal Quality / Risk Filters  
↓  
Position Manager  
↓  
Paper Trade Execution  
↓  
Trade & Signal Logs  
↓  
Forward-Test Analytics Dashboard

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

## Design Philosophy

- Risk first
- Explainability over unnecessary complexity
- Systems over isolated signals
- Separate signal generation from execution
- Measure rejected opportunities as well as executed trades
- Validate with forward data before changing strategy parameters

---

## Current Testing Stage

The engine is currently undergoing automated paper forward testing.

Rather than optimizing parameters after every observation, the current
version is being allowed to accumulate unseen market observations.

Initial review checkpoints:

- 50 completed candle checks
- 100 completed candle checks
- First qualifying paper trades
- Sufficient closed trades for meaningful performance analysis

No real capital is being deployed.

---

## Technology

- Python
- pandas
- Streamlit
- CSV-based persistent logging
- Automated scheduled execution
- Git / GitHub

---

## Limitations

- Current forward-test sample size is still small
- The system is rule-based rather than predictive
- Results may vary significantly across market regimes and assets
- Historical or paper performance does not guarantee live performance
- Transaction costs, liquidity, slippage, and execution behaviour require
  further validation before any live deployment

---

## Roadmap

- Expand forward-test dataset
- Validate strategy behaviour across additional market conditions
- Improve trade and rejection analytics
- Add multi-asset monitoring
- Compare regime-specific performance
- Strengthen risk analytics
- Explore statistical regime models
- Investigate machine-learning classification after establishing a
  reliable rule-based baseline

---

## Project Status

**Active Development — Automated Paper Forward Testing**

The current priority is collecting forward-test evidence and evaluating
whether the strategy behaves as expected outside its development data.