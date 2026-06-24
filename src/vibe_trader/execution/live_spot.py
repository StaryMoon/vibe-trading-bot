from __future__ import annotations

import json
import os
from typing import Any

from vibe_trader.config.schema import AppConfig
from vibe_trader.data.exchange_client import ExchangeClient
from vibe_trader.data.repository import SQLiteRepository
from vibe_trader.models import OrderIntent, OrderResult, PortfolioState
from vibe_trader.portfolio.accounting import apply_filled_order

LIVE_CONFIRM_TEXT = "I_UNDERSTAND_REAL_MONEY_RISK"


class LiveSpotGateway:
    def __init__(self, config: AppConfig, repo: SQLiteRepository, client: ExchangeClient):
        self.config = config
        self.repo = repo
        self.client = client

    def place_order(
        self, intent: OrderIntent, state: PortfolioState
    ) -> tuple[OrderResult, PortfolioState]:
        env_error = self._env_error(state)
        if env_error:
            order = self._rejected(intent, env_error)
            self.repo.insert_order(order)
            return order, state

        try:
            raw = self.client.create_market_order(
                intent.symbol,
                intent.side,
                intent.qty,
                quote_qty=intent.quote_qty if intent.side == "buy" else None,
            )
        except Exception as exc:  # noqa: BLE001 - exchange failures must become audit records
            order = self._rejected(intent, f"live order failed: {exc}")
            self.repo.insert_order(order)
            return order, state

        order = self._parse_order(intent, raw)
        self.repo.insert_order(order)
        new_state = apply_filled_order(self.config, self.repo, state, order)
        self.repo.insert_snapshot(
            new_state, {"last_order": order.exchange_order_id, "mode": "live"}
        )
        return order, new_state

    def _env_error(self, state: PortfolioState) -> str | None:
        prefix = self.config.exchange.name.upper()
        if not os.getenv(f"{prefix}_API_KEY") or not os.getenv(f"{prefix}_SECRET"):
            return f"missing {prefix}_API_KEY/{prefix}_SECRET for live trading"
        if self.config.exchange.sandbox:
            return "live mode requires exchange.sandbox=false"
        if self.config.trading_mode != "live" or not self.config.risk.allow_live_trading:
            return "live trading is not enabled in config"
        if os.getenv("LIVE_TRADING_ACK", "").lower() != "true":
            return "LIVE_TRADING_ACK must be true"
        if os.getenv("LIVE_TRADING_CONFIRM_TEXT") != LIVE_CONFIRM_TEXT:
            return f"LIVE_TRADING_CONFIRM_TEXT must be {LIVE_CONFIRM_TEXT}"
        max_live_equity = float(os.getenv("MAX_LIVE_EQUITY", "0") or 0)
        if max_live_equity <= 0:
            return "MAX_LIVE_EQUITY must be > 0"
        if state.equity > max_live_equity:
            return f"equity {state.equity:.2f} exceeds MAX_LIVE_EQUITY {max_live_equity:.2f}"
        return None

    def _parse_order(self, intent: OrderIntent, raw: dict[str, Any]) -> OrderResult:
        raw_status = str(raw.get("status") or "").lower()
        status_map = {"closed": "filled", "canceled": "canceled", "open": "open"}
        status = status_map.get(raw_status, raw_status or "submitted")
        filled = float(raw.get("filled") or raw.get("amount") or intent.qty or 0.0)
        avg = float(raw.get("average") or raw.get("price") or intent.reference_price)
        fee = 0.0
        raw_fee = raw.get("fee")
        if isinstance(raw_fee, dict):
            fee = float(raw_fee.get("cost") or 0.0)
        if not fee:
            fee = filled * avg * (self.config.execution.fee_bps / 10_000)
        return OrderResult(
            run_id=intent.run_id,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            status=status,
            qty=intent.qty,
            price=intent.reference_price,
            filled_qty=filled,
            avg_price=avg,
            fee=fee,
            reason=intent.reason,
            exchange_order_id=str(raw.get("id") or ""),
            message=json.dumps(
                {"mode": "live", "raw_status": raw_status, "raw_order": raw},
                ensure_ascii=False,
                default=str,
            ),
        )

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
            message=json.dumps({"error": message, "mode": "live"}, ensure_ascii=False),
        )
