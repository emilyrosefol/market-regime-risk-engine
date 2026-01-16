# src/regime_classifier.py
"""
Regime Classifier (v1)
Labels each bar as one of:
- VOLATILE: movement is unusually large (stormy)
- TREND: not volatile + drifting mostly one way (sunny)
- RANGE: not volatile + sideways (cloudy)
- UNCERTAIN: not enough data yet
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

@dataclass
class RegimeConfig:
    # How many bars to use for volatility calculation (returns spread)
    lookback_vol: int = 20
    # How many bars to use for trend slope calculation
    lookback_trend: int = 40

    # Volatility threshold: we compare current vol to "typical vol"
    # If current_vol > typical_vol * vol_mult_high -> VOLATILE
    typical_vol_window: int = 100
    vol_mult_high: float = 1.5

    # Slope threshold: if abs(slope) > slope_threshold -> TREND else RANGE
    # (slope here is average price change per bar)
    slope_threshold: float = 0.0  # if 0, we’ll auto-pick one


def simple_returns(close: pd.Series) -> pd.Series:
    """
    Simple returns: (p_t / p_{t-1}) - 1
    Example: 100 -> 105 => 0.05 (5%)
    """
    close = close.astype(float)
    return close.pct_change()


def rolling_volatility(returns: pd.Series, window: int) -> pd.Series:
    """Rolling standard deviation of returns."""
    return returns.rolling(window).std()


def simple_slope(close: pd.Series, lookback: int) -> pd.Series:
    """
    Very simple slope:
    (close[t] - close[t-lookback]) / lookback
    """
    close = close.astype(float)
    return (close - close.shift(lookback)) / float(lookback)


def classify_regimes(close: pd.Series, cfg: Optional[RegimeConfig] = None) -> pd.Series:
    """
    Returns a pd.Series of regime labels aligned with `close` index.
    """
    cfg = cfg or RegimeConfig()

    r = simple_returns(close)
    vol = rolling_volatility(r, cfg.lookback_vol)

    # Typical volatility baseline (rolling median is stable)
    typical_vol = vol.rolling(cfg.typical_vol_window).median()

    slope = simple_slope(close, cfg.lookback_trend)

    # If slope_threshold isn't set, auto-pick something reasonable:
    # use median abs(slope) over recent history as “what’s normal”
    if cfg.slope_threshold <= 0:
        slope_threshold = slope.abs().rolling(200).median()
    else:
        slope_threshold = pd.Series(cfg.slope_threshold, index=close.index)

    labels = pd.Series(index=close.index, dtype="object")

    # Need enough data first
    min_bars_needed = max(cfg.lookback_trend + 1, cfg.typical_vol_window + cfg.lookback_vol + 1)

    # Default: UNCERTAIN until we have enough bars
    labels[:] = "UNCERTAIN"

    if len(close) < min_bars_needed:
        return labels

    # Core logic:
    # 1) VOLATILE if current vol is much higher than typical
    volatile_mask = (vol > (typical_vol * cfg.vol_mult_high))

    # 2) TREND if not volatile and slope is “big enough”
    trend_mask = (~volatile_mask) & (slope.abs() > slope_threshold)

    # 3) RANGE if not volatile and slope is small
    range_mask = (~volatile_mask) & (slope.abs() <= slope_threshold)

    labels[volatile_mask] = "VOLATILE"
    labels[trend_mask] = "TREND"
    labels[range_mask] = "RANGE"

    return labels
