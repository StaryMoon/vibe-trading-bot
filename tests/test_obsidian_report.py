from __future__ import annotations

from pathlib import Path

from vibe_trader.config.schema import AppConfig
from vibe_trader.data.repository import SQLiteRepository
from vibe_trader.models import PortfolioState
from vibe_trader.reporting.obsidian import ObsidianReporter


def test_obsidian_report_is_written(tmp_path: Path) -> None:
    cfg = AppConfig()
    cfg.root_dir = tmp_path
    cfg.database.path = Path("test.sqlite3")
    cfg.reporting.dashboard_file = Path("reports/account_dashboard.md")
    cfg.reporting.obsidian_dir = Path("reports")
    repo = SQLiteRepository(cfg)
    repo.init_db()
    repo.insert_snapshot(PortfolioState(cash=1000, equity=1000, positions_value=0, positions={}))
    path = ObsidianReporter(cfg, repo).render()
    assert path.exists()
    assert "Account Overview" in path.read_text(encoding="utf-8")
