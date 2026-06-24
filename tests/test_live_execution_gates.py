from __future__ import annotations

from pathlib import Path

from vibe_trader.config.schema import AppConfig
from vibe_trader.data.exchange_client import ExchangeClient
from vibe_trader.data.repository import SQLiteRepository
from vibe_trader.execution.gateway import create_gateway
from vibe_trader.execution.live_spot import LiveSpotGateway
from vibe_trader.models import OrderIntent, PortfolioState


def _live_config(tmp_path: Path) -> AppConfig:
    cfg = AppConfig(
        trading_mode="live",
        risk={"allow_live_trading": True},
        exchange={"name": "binance", "sandbox": False},
    )
    cfg.root_dir = tmp_path
    cfg.database.path = Path("live.sqlite3")
    return cfg


def test_live_gateway_rejects_without_env_gates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_SECRET", raising=False)
    cfg = _live_config(tmp_path)
    repo = SQLiteRepository(cfg)
    repo.init_db()
    gateway = LiveSpotGateway(cfg, repo, ExchangeClient(cfg))
    intent = OrderIntent(
        run_id="run",
        symbol="BTC/USDT",
        side="buy",
        order_type="market",
        qty=0.001,
        quote_qty=10,
        reference_price=50_000,
        reason="test",
    )
    order, state = gateway.place_order(
        intent, PortfolioState(cash=50, equity=50, positions_value=0, positions={})
    )
    assert order.status == "rejected"
    assert "missing BINANCE_API_KEY" in order.message
    assert state.cash == 50


def test_create_gateway_returns_live_gateway(tmp_path: Path) -> None:
    cfg = _live_config(tmp_path)
    repo = SQLiteRepository(cfg)
    repo.init_db()
    gateway = create_gateway(cfg, repo, ExchangeClient(cfg))
    assert isinstance(gateway, LiveSpotGateway)
