from __future__ import annotations

import pandas as pd

from vibe_trader.analysis.performance import summarize_performance


def test_performance_summary_computes_trade_and_drawdown_metrics() -> None:
    orders = [
        {
            "side": "buy",
            "status": "filled",
            "fee": 0.10,
            "message": "{}",
        },
        {
            "side": "sell",
            "status": "filled",
            "fee": 0.12,
            "message": '{"realized_pnl": 5.0}',
        },
        {
            "side": "sell",
            "status": "filled",
            "fee": 0.08,
            "message": '{"realized_pnl": -2.0}',
        },
        {
            "side": "sell",
            "status": "rejected",
            "fee": 0.0,
            "message": '{"realized_pnl": 99.0}',
        },
    ]
    curve = pd.DataFrame({"equity": [100.0, 110.0, 104.0, 120.0, 114.0]})
    summary = summarize_performance(orders, curve, initial_equity=100.0)

    assert summary.total_orders == 4
    assert summary.filled_orders == 3
    assert summary.closed_trades == 2
    assert summary.wins == 1
    assert summary.losses == 1
    assert summary.realized_pnl == 3.0
    assert summary.fees == 0.30
    assert summary.win_rate == 0.5
    assert summary.profit_factor == 2.5
    assert round(summary.return_pct, 4) == 0.14
    assert round(summary.max_drawdown_pct, 4) == -0.0545
    assert round(summary.current_drawdown_pct, 4) == -0.05


def test_performance_summary_handles_empty_history() -> None:
    summary = summarize_performance([], pd.DataFrame(), initial_equity=1000.0)

    assert summary.total_orders == 0
    assert summary.closed_trades == 0
    assert summary.start_equity == 1000.0
    assert summary.end_equity == 1000.0
    assert summary.max_drawdown_pct == 0.0
    assert summary.status_label == "collecting-data"
