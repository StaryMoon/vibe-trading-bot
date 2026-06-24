from __future__ import annotations

from vibe_trader.config.schema import AppConfig
from vibe_trader.data.exchange_client import ExchangeClient
from vibe_trader.models import PortfolioState, ReconciliationResult


class ReconciliationService:
    def __init__(self, config: AppConfig, client: ExchangeClient):
        self.config = config
        self.client = client

    def check(self, state: PortfolioState) -> ReconciliationResult:
        if not self.config.risk.require_reconciliation:
            return ReconciliationResult(True, "reconciliation disabled")
        if self.config.trading_mode == "paper":
            return ReconciliationResult(True, "paper mode uses local state")

        try:
            open_orders = []
            for symbol in self.config.exchange.symbols:
                open_orders.extend(self.client.fetch_open_orders(symbol))
            if open_orders:
                return ReconciliationResult(
                    False,
                    "exchange has open orders; pause to avoid duplicate execution",
                    {"open_order_count": len(open_orders)},
                )
            balance = self.client.fetch_balance()
        except Exception as exc:  # noqa: BLE001 - external exchange errors must pause trading
            return ReconciliationResult(False, f"exchange reconciliation failed: {exc}")

        free = balance.get("free", {}) if isinstance(balance, dict) else {}
        total = balance.get("total", {}) if isinstance(balance, dict) else {}
        mismatches: dict[str, float] = {}
        for symbol in self.config.exchange.symbols:
            base = symbol.split("/")[0]
            exchange_qty = float(total.get(base, free.get(base, 0.0)) or 0.0)
            local_qty = state.positions.get(symbol).qty if symbol in state.positions else 0.0
            if abs(exchange_qty - local_qty) > self.config.risk.dust_base_qty:
                mismatches[symbol] = exchange_qty - local_qty
        if mismatches:
            return ReconciliationResult(
                False,
                "local positions differ from exchange balances",
                {"mismatches": mismatches},
            )
        return ReconciliationResult(True, "local and exchange state match")
