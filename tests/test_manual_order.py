from __future__ import annotations

from pathlib import Path

from vibe_trader.app import TradingApp
from vibe_trader.config.schema import AppConfig


def test_manual_paper_buy_executes_through_risk_engine(tmp_path: Path) -> None:
    cfg = AppConfig()
    cfg.root_dir = tmp_path
    cfg.database.path = Path("manual.sqlite3")
    cfg.exchange.ohlcv_limit = 260
    cfg.execution.max_order_quote = 20
    app = TradingApp(cfg)
    result = app.execute_manual_order("BTC/USDT", "buy", quote_qty=10)
    assert result.startswith("filled")
    orders = app.repo.list_recent_orders(1)
    assert orders[0]["status"] == "filled"
    assert app.repo.list_positions()["BTC/USDT"].notional > 0
