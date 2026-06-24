from __future__ import annotations

from vibe_trader.config.schema import AppConfig
from vibe_trader.strategy.backtest import SimpleBacktester


def test_backtest_writes_summary(tmp_path) -> None:
    cfg = AppConfig()
    cfg.root_dir = tmp_path
    cfg.exchange.ohlcv_limit = 90
    path = SimpleBacktester(cfg).run()
    assert path.exists()
    assert "Backtest Summary" in path.read_text(encoding="utf-8")
