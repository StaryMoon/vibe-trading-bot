from __future__ import annotations

import numpy as np
import pandas as pd

from vibe_trader.config.schema import StrategyConfig


def rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    line = ema12 - ema26
    signal = line.ewm(span=9, adjust=False).mean()
    hist = line - signal
    return line, signal, hist


def atr(df: pd.DataFrame, period: int) -> pd.Series:
    prev_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def add_indicators(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    out[f"ma{cfg.fast_ma}"] = out["close"].rolling(cfg.fast_ma).mean()
    out[f"ma{cfg.slow_ma}"] = out["close"].rolling(cfg.slow_ma).mean()
    out[f"ma{cfg.trend_ma}"] = out["close"].rolling(cfg.trend_ma).mean()
    out["rsi"] = rsi(out["close"], cfg.rsi_period)
    macd_line, macd_signal, macd_hist = macd(out["close"])
    out["macd"] = macd_line
    out["macd_signal"] = macd_signal
    out["macd_hist"] = macd_hist
    out["atr"] = atr(out, cfg.atr_period)
    out["atr_pct"] = out["atr"] / out["close"]
    out["volume_ma"] = out["volume"].rolling(cfg.volume_ma).mean()
    out["volume_ratio"] = out["volume"] / out["volume_ma"]
    out["return"] = out["close"].pct_change()
    out["realized_volatility"] = out["return"].rolling(20).std() * np.sqrt(20)
    return out


def latest_complete(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        raise ValueError("no candle data available")
    return df.dropna().iloc[-1]
