from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd

from vibe_trader.config.schema import AppConfig
from vibe_trader.data.exchange_client import ExchangeClient
from vibe_trader.data.repository import SQLiteRepository
from vibe_trader.indicators.technicals import add_indicators


@dataclass(frozen=True)
class DataQualityReport:
    ok: bool
    message: str
    details: dict[str, str | float] = field(default_factory=dict)


class MarketDataService:
    def __init__(self, config: AppConfig, repo: SQLiteRepository, client: ExchangeClient):
        self.config = config
        self.repo = repo
        self.client = client

    def refresh(self) -> dict[str, dict[str, pd.DataFrame]]:
        frames: dict[str, dict[str, pd.DataFrame]] = {}
        for symbol in self.config.exchange.symbols:
            frames[symbol] = {}
            for timeframe in self.config.exchange.timeframes:
                df = self.client.fetch_ohlcv(symbol, timeframe, self.config.exchange.ohlcv_limit)
                self.repo.upsert_candles(symbol, timeframe, df)
                stored = self.repo.load_candles(symbol, timeframe, self.config.exchange.ohlcv_limit)
                frames[symbol][timeframe] = add_indicators(stored, self.config.strategy)
        return frames

    def latest_prices(self, frames: dict[str, dict[str, pd.DataFrame]]) -> dict[str, float]:
        prices: dict[str, float] = {}
        for symbol, by_timeframe in frames.items():
            frame = (
                by_timeframe["15m"]
                if "15m" in by_timeframe
                else next(iter(by_timeframe.values()))
            )
            prices[symbol] = float(frame.iloc[-1]["close"])
        return prices

    def check_quality(self, symbol: str, frame: pd.DataFrame) -> DataQualityReport:
        if frame.empty:
            return DataQualityReport(False, "missing candle data", {"symbol": symbol})
        latest = frame.iloc[-1]
        previous = frame.iloc[-2] if len(frame) >= 2 else latest
        gap = abs(float(latest["close"]) / float(previous["close"]) - 1)
        if gap > self.config.risk.max_price_gap_pct:
            return DataQualityReport(
                False,
                f"price gap {gap:.2%} exceeds limit",
                {"gap": gap, "limit": self.config.risk.max_price_gap_pct},
            )
        latest_ts = frame.index[-1]
        if isinstance(latest_ts, pd.Timestamp):
            age_minutes = (datetime.now(UTC) - latest_ts.to_pydatetime()).total_seconds() / 60
            if age_minutes > self.config.risk.stale_candle_minutes:
                return DataQualityReport(
                    False,
                    f"latest candle is stale: {age_minutes:.1f} minutes",
                    {"age_minutes": age_minutes},
                )
        if latest[["open", "high", "low", "close", "volume"]].isna().any():
            return DataQualityReport(False, "latest candle contains NaN values")
        return DataQualityReport(True, "ok", {"gap": gap})
