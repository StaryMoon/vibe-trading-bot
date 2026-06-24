from __future__ import annotations

import hashlib
import math
import os
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from vibe_trader.config.schema import AppConfig
from vibe_trader.utils.time import floor_timestamp


class ExchangeClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self.exchange: Any | None = None

    def _create_ccxt_exchange(self) -> Any:
        import ccxt  # imported lazily so local demo tests do not need network clients

        exchange_name = self.config.exchange.name
        exchange_cls = getattr(ccxt, exchange_name)
        params: dict[str, Any] = {
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
        prefix = exchange_name.upper()
        api_key = os.getenv(f"{prefix}_API_KEY")
        secret = os.getenv(f"{prefix}_SECRET")
        password = os.getenv(f"{prefix}_PASSWORD")
        if api_key and secret:
            params["apiKey"] = api_key
            params["secret"] = secret
        if password:
            params["password"] = password

        exchange = exchange_cls(params)
        if self.config.exchange.sandbox:
            # CCXT requires sandbox mode to be enabled immediately after construction.
            exchange.set_sandbox_mode(True)
        return exchange

    def get_exchange(self) -> Any:
        if self.exchange is None:
            self.exchange = self._create_ccxt_exchange()
        return self.exchange

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        if self.config.exchange.name == "synthetic":
            return self._synthetic_ohlcv(symbol, timeframe, limit)
        exchange = self.get_exchange()
        raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df.set_index("timestamp").astype(float)

    def fetch_ticker_price(self, symbol: str) -> float:
        if self.config.exchange.name == "synthetic":
            df = self._synthetic_ohlcv(symbol, "15m", 2)
            return float(df.iloc[-1]["close"])
        ticker = self.get_exchange().fetch_ticker(symbol)
        return float(ticker["last"] or ticker["close"])

    def fetch_balance(self) -> dict[str, Any]:
        if self.config.exchange.name == "synthetic":
            return {
                "free": {
                    self.config.portfolio.quote_currency: self.config.portfolio.initial_cash
                }
            }
        return self.get_exchange().fetch_balance()

    def fetch_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        if self.config.exchange.name == "synthetic":
            return []
        return self.get_exchange().fetch_open_orders(symbol)

    def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        quote_qty: float | None = None,
    ) -> dict[str, Any]:
        if self.config.exchange.name == "synthetic":
            raise RuntimeError("synthetic exchange cannot submit live orders")
        exchange = self.get_exchange()
        exchange.load_markets()

        if side == "buy" and quote_qty and hasattr(exchange, "create_market_buy_order_with_cost"):
            cost = float(exchange.cost_to_precision(symbol, quote_qty))
            return exchange.create_market_buy_order_with_cost(symbol, cost)

        amount = float(exchange.amount_to_precision(symbol, amount))
        if amount <= 0:
            raise ValueError(f"order amount rounded to zero for {symbol}")
        return exchange.create_order(symbol, "market", side, amount)

    def _synthetic_ohlcv(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        seed_raw = f"{self.config.exchange.synthetic_seed}:{symbol}:{timeframe}".encode()
        seed = int(hashlib.sha256(seed_raw).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        timeframe_minutes = {"15m": 15, "1h": 60, "4h": 240}.get(timeframe, 15)
        now = floor_timestamp(pd.Timestamp(datetime.now(UTC)), timeframe)
        idx = pd.date_range(end=now, periods=limit, freq=f"{timeframe_minutes}min", tz=UTC)

        base = 63000.0 if symbol.startswith("BTC") else 3400.0
        drift = 0.00015 if symbol.startswith("BTC") else 0.00022
        cycle = np.sin(np.linspace(0, math.pi * 4, limit)) * 0.012
        noise = rng.normal(0, 0.0045, limit).cumsum()
        close = base * (1 + drift * np.arange(limit) + cycle + noise)
        open_ = np.roll(close, 1)
        open_[0] = close[0] * (1 - rng.normal(0, 0.002))
        spread = np.maximum(close * np.abs(rng.normal(0.003, 0.001, limit)), close * 0.001)
        high = np.maximum(open_, close) + spread
        low = np.minimum(open_, close) - spread
        volume = np.maximum(rng.normal(120, 25, limit), 10)
        return pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=pd.Index(idx, name="timestamp"),
        )
