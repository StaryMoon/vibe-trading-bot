from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from vibe_trader.config.schema import StrategyConfig
from vibe_trader.models import Position, TradingSignal
from vibe_trader.strategy.base import Strategy
from vibe_trader.strategy.signal import compact_snapshot


class TrendRsiMacdStrategy(Strategy):
    def __init__(self, config: StrategyConfig):
        self.config = config

    def generate(
        self,
        run_id: str,
        symbol: str,
        frames: dict[str, pd.DataFrame],
        position: Position | None,
    ) -> TradingSignal:
        required = {"15m", "1h", "4h"}
        if not required.issubset(frames):
            return self._hold(run_id, symbol, "missing required timeframes", {})

        try:
            row_15m = self._ready_row(frames["15m"])
            row_1h = self._ready_row(frames["1h"])
            row_4h = self._ready_row(frames["4h"])
        except ValueError as exc:
            return self._hold(run_id, symbol, str(exc), {})

        fast = f"ma{self.config.fast_ma}"
        slow = f"ma{self.config.slow_ma}"

        trend_ok = row_4h["close"] > row_4h[slow] and row_4h[fast] > row_4h[slow]
        confirm_ok = (
            row_1h["macd_hist"] > 0
            and self.config.rsi_entry_min <= row_1h["rsi"] <= self.config.rsi_entry_max
        )
        trigger_ok = (
            row_15m["close"] > row_15m[fast]
            and row_15m["volume_ratio"] >= self.config.min_volume_ratio
            and row_15m["atr_pct"] < 0.04
        )
        exit_by_stop = bool(position and row_15m["close"] <= position.stop_loss)
        exit_by_take_profit = bool(position and row_15m["close"] >= position.take_profit)
        exit_by_trend_break = bool(
            position
            and (
                row_1h["close"] < row_1h[slow]
                or row_1h["rsi"] < self.config.rsi_exit_min
                or (row_1h["macd_hist"] < 0 and not trend_ok)
            )
        )

        details = {
            "generated_at": datetime.now(UTC).isoformat(),
            "4h": compact_snapshot(row_4h),
            "1h": compact_snapshot(row_1h),
            "15m": compact_snapshot(row_15m),
            "conditions": {
                "trend_ok": bool(trend_ok),
                "confirm_ok": bool(confirm_ok),
                "trigger_ok": bool(trigger_ok),
                "exit_by_stop": exit_by_stop,
                "exit_by_take_profit": exit_by_take_profit,
                "exit_by_trend_break": exit_by_trend_break,
            },
        }

        if position and (exit_by_stop or exit_by_take_profit or exit_by_trend_break):
            reason_bits = []
            if exit_by_stop:
                reason_bits.append("触发止损")
            if exit_by_take_profit:
                reason_bits.append("触发止盈")
            if exit_by_trend_break:
                reason_bits.append("1h 趋势/动量转弱")
            return TradingSignal(
                run_id=run_id,
                symbol=symbol,
                action="EXIT",
                confidence=0.78,
                reason="；".join(reason_bits),
                details=details,
            )

        if not position and trend_ok and confirm_ok and trigger_ok:
            reason = "4h 多头趋势成立；1h MACD/RSI 确认；15m 重新站上短均线且成交量过滤通过"
            return TradingSignal(
                run_id=run_id,
                symbol=symbol,
                action="BUY",
                confidence=0.72,
                reason=reason,
                details=details,
            )

        blockers = []
        if position:
            blockers.append("已有持仓，等待止盈/止损/趋势退出")
        if not trend_ok:
            blockers.append("4h 趋势未通过")
        if not confirm_ok:
            blockers.append("1h 动量未确认")
        if not trigger_ok:
            blockers.append("15m 入场触发未通过")
        return TradingSignal(
            run_id=run_id,
            symbol=symbol,
            action="HOLD",
            confidence=0.5,
            reason="；".join(blockers) or "无明确动作",
            details=details,
        )

    def _ready_row(self, df: pd.DataFrame) -> pd.Series:
        fast = f"ma{self.config.fast_ma}"
        slow = f"ma{self.config.slow_ma}"
        required = ["close", fast, slow, "rsi", "macd_hist", "atr_pct", "volume_ratio"]
        ready = df.dropna(subset=[column for column in required if column in df.columns])
        if ready.empty:
            raise ValueError("not enough indicator history")
        return ready.iloc[-1]

    def _hold(self, run_id: str, symbol: str, reason: str, details: dict) -> TradingSignal:
        return TradingSignal(
            run_id=run_id,
            symbol=symbol,
            action="HOLD",
            confidence=0.0,
            reason=reason,
            details=details,
        )
