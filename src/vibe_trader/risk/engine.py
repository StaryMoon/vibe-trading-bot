from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from vibe_trader.config.schema import AppConfig
from vibe_trader.data.market_data import DataQualityReport
from vibe_trader.data.repository import SQLiteRepository
from vibe_trader.models import (
    OrderIntent,
    PortfolioState,
    ReconciliationResult,
    RiskDecision,
    TradingSignal,
)


class RiskEngine:
    def __init__(self, config: AppConfig, repo: SQLiteRepository):
        self.config = config
        self.repo = repo

    def evaluate(
        self,
        signal: TradingSignal,
        state: PortfolioState,
        data_quality: DataQualityReport,
        reconciliation: ReconciliationResult,
        price: float,
        quote_override: float | None = None,
    ) -> RiskDecision:
        if signal.action == "HOLD":
            return RiskDecision(False, "NO_ACTION", signal.reason)

        live_decision = self._check_live_gate(state)
        if live_decision:
            return live_decision

        if not data_quality.ok:
            return RiskDecision(
                False,
                "REJECTED_DATA_ANOMALY",
                data_quality.message,
                details=data_quality.details,
            )
        if not reconciliation.ok:
            return RiskDecision(
                False,
                "REJECTED_RECONCILIATION_FAILED",
                reconciliation.message,
                details=reconciliation.details,
            )
        if self.repo.open_orders_for_symbol(signal.symbol):
            return RiskDecision(False, "REJECTED_DUPLICATE_ORDER", "local open order exists")

        cooldown = self._cooldown_remaining(signal.symbol)
        if cooldown.total_seconds() > 0:
            return RiskDecision(
                False,
                "REJECTED_COOLDOWN",
                f"cooldown remaining {cooldown.total_seconds() / 60:.1f} minutes",
            )

        daily_limit = -state.equity * self.config.risk.max_daily_loss_pct
        if state.daily_pnl <= daily_limit:
            return RiskDecision(
                False,
                "REJECTED_DAILY_LOSS_LIMIT",
                f"daily pnl {state.daily_pnl:.2f} <= limit {daily_limit:.2f}",
            )

        if state.consecutive_losses >= self.config.risk.max_consecutive_losses:
            return RiskDecision(
                False,
                "REJECTED_CONSECUTIVE_LOSSES",
                f"consecutive losses {state.consecutive_losses} reached limit",
            )

        if signal.action == "EXIT":
            return self._exit_intent(signal, state, price)
        if signal.action == "BUY":
            return self._buy_intent(signal, state, price, quote_override)
        return RiskDecision(False, "REJECTED_UNKNOWN_SIGNAL", f"unsupported signal {signal.action}")

    def _buy_intent(
        self,
        signal: TradingSignal,
        state: PortfolioState,
        price: float,
        quote_override: float | None = None,
    ) -> RiskDecision:
        if signal.symbol in state.positions:
            return RiskDecision(False, "REJECTED_ALREADY_IN_POSITION", "position already exists")

        configured_quote = state.equity * self.config.execution.quote_order_size_pct
        requested_quote = configured_quote if quote_override is None else quote_override
        if requested_quote <= 0:
            return RiskDecision(False, "REJECTED_ORDER_TOO_SMALL", "requested quote is <= 0")
        target_quote = min(
            requested_quote,
            self.config.execution.max_order_quote,
            state.equity * self.config.risk.max_symbol_exposure_pct,
        )
        if target_quote < self.config.risk.min_quote_balance:
            return RiskDecision(
                False, "REJECTED_ORDER_TOO_SMALL", "target order is below minimum quote"
            )
        if target_quote > state.cash - self.config.risk.min_quote_balance:
            return RiskDecision(False, "REJECTED_CASH_LIMIT", "not enough cash after reserve")

        total_after = state.positions_value + target_quote
        if total_after > state.equity * self.config.risk.max_total_exposure_pct:
            return RiskDecision(False, "REJECTED_TOTAL_EXPOSURE", "total exposure limit exceeded")

        potential_loss = target_quote * self.config.strategy.stop_loss_pct
        if potential_loss > state.equity * self.config.risk.max_single_trade_loss_pct:
            return RiskDecision(
                False,
                "REJECTED_SINGLE_TRADE_LOSS",
                "configured stop loss exceeds single-trade risk budget",
                details={"potential_loss": potential_loss},
            )

        qty = target_quote / price
        intent = OrderIntent(
            run_id=signal.run_id,
            symbol=signal.symbol,
            side="buy",
            order_type=self.config.execution.order_type,
            qty=qty,
            quote_qty=target_quote,
            reference_price=price,
            reason=signal.reason,
        )
        return RiskDecision(True, "APPROVED", "risk checks passed", intent)

    def _exit_intent(
        self, signal: TradingSignal, state: PortfolioState, price: float
    ) -> RiskDecision:
        position = state.positions.get(signal.symbol)
        if not position:
            return RiskDecision(False, "REJECTED_NO_POSITION", "no position to exit")
        intent = OrderIntent(
            run_id=signal.run_id,
            symbol=signal.symbol,
            side="sell",
            order_type=self.config.execution.order_type,
            qty=position.qty,
            quote_qty=position.qty * price,
            reference_price=price,
            reason=signal.reason,
        )
        return RiskDecision(True, "APPROVED", "exit approved", intent)

    def _check_live_gate(self, state: PortfolioState) -> RiskDecision | None:
        if self.config.trading_mode != "live":
            return None
        if not self.config.risk.allow_live_trading:
            return RiskDecision(False, "REJECTED_LIVE_GATE", "live trading disabled by config")
        if os.getenv("LIVE_TRADING_ACK", "").lower() != "true":
            return RiskDecision(False, "REJECTED_LIVE_GATE", "LIVE_TRADING_ACK is not true")
        max_live_equity = float(os.getenv("MAX_LIVE_EQUITY", "0") or 0)
        if max_live_equity <= 0 or state.equity > max_live_equity:
            return RiskDecision(False, "REJECTED_LIVE_GATE", "live equity exceeds env cap")
        return None

    def _cooldown_remaining(self, symbol: str) -> timedelta:
        last = self.repo.last_order_for_symbol(symbol)
        if not last or last.get("status") != "filled":
            return timedelta(0)
        created_at = datetime.fromisoformat(last["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        next_allowed = created_at + timedelta(minutes=self.config.risk.cooldown_minutes)
        return max(next_allowed - datetime.now(UTC), timedelta(0))
