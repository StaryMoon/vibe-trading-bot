from __future__ import annotations

from vibe_trader.config.schema import AppConfig
from vibe_trader.strategy.base import Strategy
from vibe_trader.strategy.trend_rsi_macd import TrendRsiMacdStrategy


def create_strategy(config: AppConfig) -> Strategy:
    if config.strategy.name != "trend_rsi_macd":
        raise ValueError(f"unsupported strategy: {config.strategy.name}")
    return TrendRsiMacdStrategy(config.strategy)
