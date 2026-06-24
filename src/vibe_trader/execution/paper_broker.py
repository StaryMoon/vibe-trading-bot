from __future__ import annotations

import json

from vibe_trader.config.schema import AppConfig
from vibe_trader.data.repository import SQLiteRepository
from vibe_trader.models import OrderIntent, OrderResult, PortfolioState
from vibe_trader.portfolio.accounting import apply_filled_order


class PaperBroker:
    def __init__(self, config: AppConfig, repo: SQLiteRepository):
        self.config = config
        self.repo = repo

    def place_order(
        self, intent: OrderIntent, state: PortfolioState
    ) -> tuple[OrderResult, PortfolioState]:
        slippage = self.config.execution.slippage_bps / 10_000
        fee_rate = self.config.execution.fee_bps / 10_000
        if intent.side == "buy":
            fill_price = intent.reference_price * (1 + slippage)
            filled_qty = intent.quote_qty / fill_price
            fee = intent.quote_qty * fee_rate
            total_cost = intent.quote_qty + fee
            if total_cost > state.cash:
                order = self._rejected(intent, "insufficient paper cash")
                self.repo.insert_order(order)
                return order, state
            status = "filled"
            realized_pnl = 0.0
        else:
            position = state.positions.get(intent.symbol)
            if not position:
                order = self._rejected(intent, "no local position to sell")
                self.repo.insert_order(order)
                return order, state
            fill_price = intent.reference_price * (1 - slippage)
            filled_qty = min(intent.qty, position.qty)
            gross = filled_qty * fill_price
            fee = gross * fee_rate
            realized_pnl = (fill_price - position.entry_price) * filled_qty - fee
            status = "filled"

        order = OrderResult(
            run_id=intent.run_id,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            status=status,
            qty=intent.qty,
            price=intent.reference_price,
            filled_qty=filled_qty,
            avg_price=fill_price,
            fee=fee,
            reason=intent.reason,
            exchange_order_id=f"paper-{intent.run_id[:8]}-{intent.symbol.replace('/', '')}",
            message=json.dumps({"realized_pnl": realized_pnl, "mode": "paper"}, ensure_ascii=False),
        )
        self.repo.insert_order(order)
        new_state = apply_filled_order(self.config, self.repo, state, order)
        self.repo.insert_snapshot(new_state, {"last_order": order.exchange_order_id})
        return order, new_state

    def _rejected(self, intent: OrderIntent, message: str) -> OrderResult:
        return OrderResult(
            run_id=intent.run_id,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            status="rejected",
            qty=intent.qty,
            price=intent.reference_price,
            filled_qty=0.0,
            avg_price=0.0,
            fee=0.0,
            reason=intent.reason,
            exchange_order_id="",
            message=json.dumps({"error": message, "mode": "paper"}, ensure_ascii=False),
        )
