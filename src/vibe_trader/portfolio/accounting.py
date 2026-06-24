from __future__ import annotations

from dataclasses import replace

from vibe_trader.config.schema import AppConfig
from vibe_trader.data.exchange_client import ExchangeClient
from vibe_trader.data.repository import SQLiteRepository, utc_now_iso
from vibe_trader.models import OrderResult, PortfolioState, Position


class PortfolioService:
    def __init__(
        self,
        config: AppConfig,
        repo: SQLiteRepository,
        client: ExchangeClient | None = None,
    ):
        self.config = config
        self.repo = repo
        self.client = client

    def load_state(self, prices: dict[str, float]) -> PortfolioState:
        positions = self.repo.list_positions()
        marked_positions: dict[str, Position] = {}
        for symbol, position in positions.items():
            mark = float(prices.get(symbol, position.mark_price))
            unrealized = (mark - position.entry_price) * position.qty
            marked = replace(
                position,
                mark_price=mark,
                unrealized_pnl=unrealized,
                updated_at=utc_now_iso(),
            )
            self.repo.upsert_position(marked)
            marked_positions[symbol] = marked

        latest = self.repo.latest_snapshot()
        cash = float(latest["cash"]) if latest else self.config.portfolio.initial_cash
        if self.config.trading_mode in {"sandbox", "live"} and self.client is not None:
            balance = self.client.fetch_balance()
            free = balance.get("free", {}) if isinstance(balance, dict) else {}
            cash = float(free.get(self.config.portfolio.quote_currency, 0.0) or 0.0)
        positions_value = sum(p.notional for p in marked_positions.values())
        realized_today = self.repo.today_realized_pnl()
        unrealized = sum(p.unrealized_pnl for p in marked_positions.values())
        return PortfolioState(
            cash=cash,
            equity=cash + positions_value,
            positions_value=positions_value,
            positions=marked_positions,
            daily_pnl=realized_today + unrealized,
            consecutive_losses=self.repo.consecutive_loss_count(),
        )

    def save_snapshot(self, state: PortfolioState, details: dict | None = None) -> None:
        self.repo.insert_snapshot(state, details)


def apply_filled_order(
    config: AppConfig,
    repo: SQLiteRepository,
    state: PortfolioState,
    order: OrderResult,
) -> PortfolioState:
    positions = dict(state.positions)
    cash = state.cash
    position = positions.get(order.symbol)
    realized_pnl = 0.0

    if order.status != "filled" or order.filled_qty <= 0:
        return state

    if order.side == "buy":
        cost = order.filled_qty * order.avg_price + order.fee
        cash -= cost
        if position:
            new_qty = position.qty + order.filled_qty
            avg_entry = (
                (position.qty * position.entry_price)
                + (order.filled_qty * order.avg_price)
            ) / new_qty
            position = replace(
                position,
                qty=new_qty,
                entry_price=avg_entry,
                mark_price=order.avg_price,
                updated_at=utc_now_iso(),
                stop_loss=avg_entry * (1 - config.strategy.stop_loss_pct),
                take_profit=avg_entry * (1 + config.strategy.take_profit_pct),
            )
        else:
            position = Position(
                symbol=order.symbol,
                side="long",
                qty=order.filled_qty,
                entry_price=order.avg_price,
                mark_price=order.avg_price,
                realized_pnl=0.0,
                unrealized_pnl=0.0,
                opened_at=utc_now_iso(),
                updated_at=utc_now_iso(),
                stop_loss=order.avg_price * (1 - config.strategy.stop_loss_pct),
                take_profit=order.avg_price * (1 + config.strategy.take_profit_pct),
            )
        positions[order.symbol] = position
        repo.upsert_position(position)

    if order.side == "sell" and position:
        qty = min(order.filled_qty, position.qty)
        gross = qty * order.avg_price
        realized_pnl = (order.avg_price - position.entry_price) * qty - order.fee
        cash += gross - order.fee
        remaining_qty = position.qty - qty
        if remaining_qty <= 1e-12:
            repo.upsert_position(replace(position, qty=0))
            positions.pop(order.symbol, None)
        else:
            updated = replace(
                position,
                qty=remaining_qty,
                mark_price=order.avg_price,
                realized_pnl=position.realized_pnl + realized_pnl,
                unrealized_pnl=(order.avg_price - position.entry_price) * remaining_qty,
                updated_at=utc_now_iso(),
            )
            positions[order.symbol] = updated
            repo.upsert_position(updated)

    positions_value = sum(p.qty * p.mark_price for p in positions.values())
    return PortfolioState(
        cash=cash,
        equity=cash + positions_value,
        positions_value=positions_value,
        positions=positions,
        daily_pnl=state.daily_pnl + realized_pnl,
        consecutive_losses=state.consecutive_losses,
    )
