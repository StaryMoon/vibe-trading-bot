from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vibe_trader.analysis.performance import PerformanceSummary, summarize_performance
from vibe_trader.config.schema import AppConfig
from vibe_trader.data.repository import SQLiteRepository


class ObsidianReporter:
    def __init__(self, config: AppConfig, repo: SQLiteRepository):
        self.config = config
        self.repo = repo

    def render(self) -> Path:
        dashboard_path = self.config.resolve_path(self.config.reporting.dashboard_file)
        dashboard_path.parent.mkdir(parents=True, exist_ok=True)
        content = self._dashboard_markdown()
        dashboard_path.write_text(content, encoding="utf-8")

        daily_dir = self.config.resolve_path(self.config.reporting.obsidian_dir) / "daily"
        daily_dir.mkdir(parents=True, exist_ok=True)
        daily_path = daily_dir / f"{datetime.now(UTC).date().isoformat()}.md"
        daily_path.write_text(content, encoding="utf-8")
        return dashboard_path

    def _dashboard_markdown(self) -> str:
        snapshot = self.repo.latest_snapshot()
        positions = list(self.repo.list_positions().values())
        orders = self.repo.list_today_orders()
        signals = self.repo.list_recent_signals(12)
        risks = self.repo.list_recent_risk_events(12)
        review = self.repo.latest_review()
        performance = summarize_performance(
            self.repo.list_recent_orders(500),
            self.repo.equity_curve(30),
            self.config.portfolio.initial_cash,
        )
        now = datetime.now(UTC).isoformat()

        equity = float(snapshot["equity"]) if snapshot else self.config.portfolio.initial_cash
        cash = float(snapshot["cash"]) if snapshot else self.config.portfolio.initial_cash
        positions_value = float(snapshot["positions_value"]) if snapshot else 0.0
        daily_pnl = float(snapshot["daily_pnl"]) if snapshot else 0.0
        risk_status = risks[0]["status"] if risks else "OK"

        sections = [
            "# Vibe Trading Dashboard",
            "",
            (
                f"> Mode: **{self.config.trading_mode}** | "
                f"Exchange: **{self.config.exchange.name}** | Last run: `{now}`"
            ),
            "",
            "## Account Overview",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Total Equity | {equity:.2f} {self.config.portfolio.quote_currency} |",
            f"| Cash | {cash:.2f} {self.config.portfolio.quote_currency} |",
            f"| Positions Value | {positions_value:.2f} {self.config.portfolio.quote_currency} |",
            f"| Today PnL | {daily_pnl:.2f} {self.config.portfolio.quote_currency} |",
            f"| Risk Status | {risk_status} |",
            "",
            "## Performance Summary",
            "",
            self._performance_table(performance),
            "",
            "## Positions",
            "",
            self._positions_table(positions),
            "",
            "## Risk Indicators",
            "",
            self._risk_table(equity),
            "",
            "## Today Operations",
            "",
            self._orders_table(orders),
            "",
            "## Latest Signals",
            "",
            self._signals_table(signals),
            "",
            "## Recent Risk Events",
            "",
            self._risks_table(risks),
            "",
            "## Daily Review",
            "",
            review["content"] if review else "- Review not generated yet.",
            "",
        ]
        return "\n".join(sections)

    def _performance_table(self, performance: PerformanceSummary) -> str:
        profit_factor = "inf"
        if performance.profit_factor != float("inf"):
            profit_factor = f"{performance.profit_factor:.2f}"
        lines = [
            "| Metric | Value |",
            "|---|---:|",
            f"| Status | {performance.status_label} |",
            f"| Filled Orders | {performance.filled_orders} / {performance.total_orders} |",
            f"| Closed Trades | {performance.closed_trades} |",
            f"| Win Rate | {performance.win_rate:.1%} |",
            f"| Realized PnL | {performance.realized_pnl:.2f} |",
            f"| Fees | {performance.fees:.4f} |",
            f"| Profit Factor | {profit_factor} |",
            f"| Return | {performance.return_pct:.2%} |",
            f"| Max Drawdown | {performance.max_drawdown_pct:.2%} |",
            f"| Current Drawdown | {performance.current_drawdown_pct:.2%} |",
        ]
        return "\n".join(lines)

    def _positions_table(self, positions: list[Any]) -> str:
        if not positions:
            return "_No open positions._"
        lines = [
            "| Symbol | Side | Qty | Entry | Mark | Unrealized PnL | Stop | Take Profit |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for p in positions:
            lines.append(
                f"| {p.symbol} | {p.side} | {p.qty:.8f} | {p.entry_price:.2f} | "
                f"{p.mark_price:.2f} | {p.unrealized_pnl:.2f} | "
                f"{p.stop_loss:.2f} | {p.take_profit:.2f} |"
            )
        return "\n".join(lines)

    def _risk_table(self, equity: float) -> str:
        risk = self.config.risk
        lines = [
            "| Rule | Current/Limit | Status |",
            "|---|---:|---|",
            f"| Max Symbol Exposure | {risk.max_symbol_exposure_pct:.1%} | configured |",
            f"| Max Total Exposure | {risk.max_total_exposure_pct:.1%} | configured |",
            (
                f"| Max Single Trade Loss | "
                f"{equity * risk.max_single_trade_loss_pct:.2f} | configured |"
            ),
            f"| Max Daily Loss | {equity * risk.max_daily_loss_pct:.2f} | configured |",
            f"| Cooldown | {risk.cooldown_minutes} min | configured |",
            f"| Consecutive Loss Pause | {risk.max_consecutive_losses} | configured |",
            (
                f"| Live Trading | "
                f"{'enabled' if self.config.trading_mode == 'live' else 'disabled'} | "
                "safety gate |"
            ),
        ]
        return "\n".join(lines)

    def _orders_table(self, orders: list[dict[str, Any]]) -> str:
        if not orders:
            return "_No operations today._"
        lines = [
            "| Time | Symbol | Side | Status | Price | Qty | Fee | Reason |",
            "|---|---|---|---|---:|---:|---:|---|",
        ]
        for o in orders[:20]:
            lines.append(
                f"| {o['created_at'][11:16]} | {o['symbol']} | {o['side']} | {o['status']} | "
                f"{o['avg_price']:.2f} | {o['filled_qty']:.8f} | {o['fee']:.4f} | {o['reason']} |"
            )
        return "\n".join(lines)

    def _signals_table(self, signals: list[dict[str, Any]]) -> str:
        if not signals:
            return "_No signals yet._"
        lines = [
            "| Time | Symbol | Action | Confidence | Reason |",
            "|---|---|---|---:|---|",
        ]
        for s in signals[:12]:
            lines.append(
                f"| {s['ts'][11:16]} | {s['symbol']} | {s['action']} | "
                f"{s['confidence']:.2f} | {s['reason']} |"
            )
        return "\n".join(lines)

    def _risks_table(self, risks: list[dict[str, Any]]) -> str:
        if not risks:
            return "_No risk events yet._"
        lines = [
            "| Time | Symbol | Rule | Status | Message |",
            "|---|---|---|---|---|",
        ]
        for r in risks[:12]:
            lines.append(
                f"| {r['created_at'][11:16]} | {r.get('symbol') or '-'} | {r['rule']} | "
                f"{r['status']} | {r['message']} |"
            )
        return "\n".join(lines)
