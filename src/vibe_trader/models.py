from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

SignalAction = Literal["BUY", "EXIT", "HOLD"]
OrderSide = Literal["buy", "sell"]


@dataclass(frozen=True)
class TradingSignal:
    run_id: str
    symbol: str
    action: SignalAction
    confidence: float
    reason: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class Position:
    symbol: str
    side: str
    qty: float
    entry_price: float
    mark_price: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    opened_at: str = ""
    updated_at: str = ""
    stop_loss: float = 0.0
    take_profit: float = 0.0

    @property
    def notional(self) -> float:
        return self.qty * self.mark_price


@dataclass(frozen=True)
class PortfolioState:
    cash: float
    equity: float
    positions_value: float
    positions: dict[str, Position]
    daily_pnl: float = 0.0
    consecutive_losses: int = 0


@dataclass(frozen=True)
class ReconciliationResult:
    ok: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    status: str
    message: str
    order_intent: OrderIntent | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderIntent:
    run_id: str
    symbol: str
    side: OrderSide
    order_type: str
    qty: float
    quote_qty: float
    reference_price: float
    reason: str


@dataclass(frozen=True)
class OrderResult:
    run_id: str
    symbol: str
    side: OrderSide
    order_type: str
    status: str
    qty: float
    price: float
    filled_qty: float
    avg_price: float
    fee: float
    reason: str
    exchange_order_id: str = ""
    message: str = ""
