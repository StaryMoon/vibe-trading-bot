from __future__ import annotations

from pathlib import Path

from vibe_trader.config.schema import AppConfig
from vibe_trader.data.market_data import DataQualityReport
from vibe_trader.data.repository import SQLiteRepository
from vibe_trader.models import PortfolioState, ReconciliationResult, TradingSignal
from vibe_trader.risk.engine import RiskEngine


def _config(tmp_path: Path) -> AppConfig:
    cfg = AppConfig()
    cfg.root_dir = tmp_path
    cfg.database.path = Path("test.sqlite3")
    return cfg


def test_risk_engine_approves_small_buy(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    repo = SQLiteRepository(cfg)
    repo.init_db()
    state = PortfolioState(cash=1000, equity=1000, positions_value=0, positions={})
    signal = TradingSignal("run", "BTC/USDT", "BUY", 0.8, "test")
    decision = RiskEngine(cfg, repo).evaluate(
        signal,
        state,
        DataQualityReport(True, "ok"),
        ReconciliationResult(True, "ok"),
        50_000,
    )
    assert decision.approved
    assert decision.order_intent is not None
    assert decision.order_intent.side == "buy"


def test_risk_engine_rejects_data_anomaly(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    repo = SQLiteRepository(cfg)
    repo.init_db()
    state = PortfolioState(cash=1000, equity=1000, positions_value=0, positions={})
    signal = TradingSignal("run", "BTC/USDT", "BUY", 0.8, "test")
    decision = RiskEngine(cfg, repo).evaluate(
        signal,
        state,
        DataQualityReport(False, "bad gap"),
        ReconciliationResult(True, "ok"),
        50_000,
    )
    assert not decision.approved
    assert decision.status == "REJECTED_DATA_ANOMALY"
