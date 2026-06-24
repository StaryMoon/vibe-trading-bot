from __future__ import annotations

import pandas as pd

from vibe_trader.config.schema import StrategyConfig
from vibe_trader.strategy.trend_rsi_macd import TrendRsiMacdStrategy


def _frame(close: float, fast: float, slow: float, rsi: float, macd_hist: float) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "close": close,
                "ma20": fast,
                "ma50": slow,
                "rsi": rsi,
                "macd_hist": macd_hist,
                "atr_pct": 0.01,
                "volume_ratio": 1.0,
                "macd": 10.0,
                "macd_signal": 9.0,
                "realized_volatility": 0.02,
            }
        ],
        index=pd.to_datetime(["2026-06-23T00:00:00Z"]),
    )


def test_trend_strategy_emits_buy_when_all_timeframes_align() -> None:
    strategy = TrendRsiMacdStrategy(StrategyConfig())
    signal = strategy.generate(
        run_id="run",
        symbol="BTC/USDT",
        frames={
            "4h": _frame(100, 90, 80, 60, 1),
            "1h": _frame(100, 90, 80, 58, 1),
            "15m": _frame(100, 90, 80, 55, 1),
        },
        position=None,
    )
    assert signal.action == "BUY"
    assert "4h" in signal.reason


def test_trend_strategy_holds_when_trend_filter_fails() -> None:
    strategy = TrendRsiMacdStrategy(StrategyConfig())
    signal = strategy.generate(
        run_id="run",
        symbol="BTC/USDT",
        frames={
            "4h": _frame(70, 75, 80, 45, -1),
            "1h": _frame(100, 90, 80, 58, 1),
            "15m": _frame(100, 90, 80, 55, 1),
        },
        position=None,
    )
    assert signal.action == "HOLD"
    assert "4h" in signal.reason
