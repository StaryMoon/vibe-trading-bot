from __future__ import annotations

from pathlib import Path

from vibe_trader.config.schema import AppConfig
from vibe_trader.data.repository import SQLiteRepository
from vibe_trader.execution.paper_broker import PaperBroker
from vibe_trader.models import OrderIntent, PortfolioState


def test_paper_buy_updates_cash_and_position(tmp_path: Path) -> None:
    cfg = AppConfig()
    cfg.root_dir = tmp_path
    cfg.database.path = Path("test.sqlite3")
    repo = SQLiteRepository(cfg)
    repo.init_db()
    state = PortfolioState(cash=1000, equity=1000, positions_value=0, positions={})
    intent = OrderIntent(
        run_id="run",
        symbol="BTC/USDT",
        side="buy",
        order_type="market",
        qty=0.001,
        quote_qty=100,
        reference_price=50_000,
        reason="unit test",
    )
    order, new_state = PaperBroker(cfg, repo).place_order(intent, state)
    assert order.status == "filled"
    assert "BTC/USDT" in new_state.positions
    assert new_state.cash < state.cash
    assert repo.list_recent_orders(1)[0]["status"] == "filled"
