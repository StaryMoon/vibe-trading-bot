from __future__ import annotations

import json

from vibe_trader.models import OrderResult


def attach_realized_pnl(order: OrderResult, realized_pnl: float) -> OrderResult:
    payload = {}
    if order.message:
        try:
            payload = json.loads(order.message)
        except json.JSONDecodeError:
            payload = {"message": order.message}
    payload["realized_pnl"] = realized_pnl
    return OrderResult(
        run_id=order.run_id,
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        status=order.status,
        qty=order.qty,
        price=order.price,
        filled_qty=order.filled_qty,
        avg_price=order.avg_price,
        fee=order.fee,
        reason=order.reason,
        exchange_order_id=order.exchange_order_id,
        message=json.dumps(payload, ensure_ascii=False),
    )
