# Market Regime Risk Engine

> A Python-based quantitative trading research engine that detects market regimes, identifies fake breakout opportunities, performs systematic backtesting, and evaluates strategy performance across multiple cryptocurrency markets.

---

# Overview

The Market Regime Risk Engine is a quantitative research project built entirely in Python to explore how market structure, volatility, and trend behavior influence trading performance.

Rather than predicting market direction with machine learning, this engine focuses on building a transparent, explainable decision framework using technical market features and systematic risk management.

The project has evolved through more than 40 development versions and continues to expand with research, validation, visualization, and paper-trading capabilities.

---

# Features

- Multi-market backtesting (BTC, ETH, SOL, ETC)
- Market regime classification
- Fake breakout detection
- ATR-based stop loss and take profit engine
- Edge scoring system
- Position sizing using fixed risk (R-based accounting)
- Walk-forward validation
- Yearly performance validation
- Market comparison analysis
- Automatic equity curve generation
- Drawdown analysis
- CSV export of trades and performance
- Research visualization with Matplotlib

---

# Project Workflow

```text
Yahoo Finance
      │
      ▼
Historical Market Data
      │
      ▼
Feature Engineering
(MA • ATR • RSI • Volatility)
      │
      ▼
Market Regime Classification
      │
      ▼
Signal Generation
(Fake Breakouts)
      │
      ▼
Execution Engine
      │
      ▼
Risk Accounting
      │
      ▼
Performance Analysis
      │
      ▼
Charts + CSV Reports
```

---

# Technologies

- Python
- Pandas
- NumPy
- Matplotlib
- yfinance
- Git
- GitHub

---

# Current Research Results

Current validation includes:

- Multi-market comparison
- Walk-forward testing
- Yearly validation
- Edge score analysis
- Equity curve visualization
- Drawdown visualization
- Automatic CSV reporting

Example outputs include:

- Market comparison charts
- Equity curves
- Drawdown curves
- Trade ledger exports

---

# Design Philosophy

The engine was designed around several principles:

- Explainability over complexity
- Risk-first decision making
- Systematic execution
- Reproducible research
- Continuous iterative improvement

Rather than fitting models to maximize historical returns, the project emphasizes understanding why strategies perform under different market regimes.

---

# Current Limitations

This project is an active research system.

Current limitations include:

- Historical backtesting only
- Simplified execution assumptions
- No slippage model
- No exchange connectivity
- No live order execution
- Limited trade sample on some markets

These limitations are intentionally documented as part of the ongoing research process.

---

# Roadmap

## Phase 1 ✅

- Historical backtesting engine
- Market comparison
- Edge scoring
- Walk-forward validation
- Research visualization

## Phase 2 (In Progress)

- GitHub portfolio improvements
- Research documentation
- Paper trading engine
- Signal logging

## Phase 3

- Live paper trading dashboard
- Portfolio-level risk management
- Multi-strategy framework
- Performance analytics dashboard

---

# About This Project

This project was built as a long-term software engineering and quantitative research initiative.

Its primary goals are:

- Improve Python software engineering skills
- Develop systematic trading research workflows
- Learn quantitative risk management
- Build a portfolio demonstrating data engineering, analytics, and algorithmic trading concepts

The project continues to evolve through iterative development, testing, and validation.

