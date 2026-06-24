from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PerformanceSummary:
    total_orders: int
    filled_orders: int
    closed_trades: int
    wins: int
    losses: int
    realized_pnl: float
    fees: float
    win_rate: float
    profit_factor: float
    average_win: float
    average_loss: float
    start_equity: float
    end_equity: float
    return_pct: float
    max_drawdown_pct: float
    current_drawdown_pct: float

    @property
    def status_label(self) -> str:
        if self.closed_trades == 0:
            return "collecting-data"
        if self.realized_pnl > 0 and self.max_drawdown_pct > -0.05:
            return "stable-positive"
        if self.current_drawdown_pct < -0.05:
            return "drawdown-watch"
        return "needs-more-samples"


def summarize_performance(
    orders: list[dict[str, Any]],
    equity_curve: pd.DataFrame,
    initial_equity: float,
) -> PerformanceSummary:
    filled = [order for order in orders if order.get("status") == "filled"]
    closed_pnls = [_realized_pnl(order) for order in filled if _is_closing_order(order)]
    wins = [pnl for pnl in closed_pnls if pnl > 0]
    losses = [pnl for pnl in closed_pnls if pnl < 0]
    gain = sum(wins)
    loss = abs(sum(losses))
    start_equity, end_equity = _equity_bounds(equity_curve, initial_equity)
    max_dd, current_dd = drawdown_stats(equity_curve)
    return PerformanceSummary(
        total_orders=len(orders),
        filled_orders=len(filled),
        closed_trades=len(closed_pnls),
        wins=len(wins),
        losses=len(losses),
        realized_pnl=sum(closed_pnls),
        fees=sum(float(order.get("fee") or 0.0) for order in filled),
        win_rate=len(wins) / len(closed_pnls) if closed_pnls else 0.0,
        profit_factor=gain / loss if loss > 0 else (float("inf") if gain > 0 else 0.0),
        average_win=gain / len(wins) if wins else 0.0,
        average_loss=sum(losses) / len(losses) if losses else 0.0,
        start_equity=start_equity,
        end_equity=end_equity,
        return_pct=(end_equity / start_equity - 1.0) if start_equity > 0 else 0.0,
        max_drawdown_pct=max_dd,
        current_drawdown_pct=current_dd,
    )


def drawdown_stats(equity_curve: pd.DataFrame) -> tuple[float, float]:
    if equity_curve.empty or "equity" not in equity_curve.columns:
        return 0.0, 0.0
    values = [float(value) for value in equity_curve["equity"].dropna().tolist()]
    if not values:
        return 0.0, 0.0
    peak = values[0]
    max_drawdown = 0.0
    current_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            current_drawdown = value / peak - 1.0
            max_drawdown = min(max_drawdown, current_drawdown)
    return max_drawdown, current_drawdown


def _equity_bounds(equity_curve: pd.DataFrame, initial_equity: float) -> tuple[float, float]:
    if equity_curve.empty or "equity" not in equity_curve.columns:
        return initial_equity, initial_equity
    values = [float(value) for value in equity_curve["equity"].dropna().tolist()]
    if not values:
        return initial_equity, initial_equity
    return values[0], values[-1]


def _is_closing_order(order: dict[str, Any]) -> bool:
    if order.get("side") == "sell":
        return True
    message = _message_payload(order)
    return "realized_pnl" in message


def _realized_pnl(order: dict[str, Any]) -> float:
    message = _message_payload(order)
    return float(message.get("realized_pnl", 0.0))


def _message_payload(order: dict[str, Any]) -> dict[str, Any]:
    raw = order.get("message") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
