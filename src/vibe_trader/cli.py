from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from vibe_trader.analysis.performance import summarize_performance
from vibe_trader.app import TradingApp
from vibe_trader.config.loader import load_config
from vibe_trader.data.repository import SQLiteRepository
from vibe_trader.scheduler.runner import run_scheduler
from vibe_trader.utils.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibe-trader")
    parser.add_argument("--config", default="configs/default.yaml", help="Path to YAML config.")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="Create or migrate SQLite tables.")
    sub.add_parser("run-once", help="Run one market/strategy/risk/reporting cycle.")
    sub.add_parser("schedule", help="Run the 15-minute scheduler.")
    sub.add_parser("dashboard", help="Open the Streamlit dashboard.")
    sub.add_parser("backtest", help="Run a simple local smoke backtest.")
    sub.add_parser("performance", help="Print recent performance and drawdown metrics.")
    sub.add_parser("doctor", help="Check local safety/configuration basics.")
    sub.add_parser("pause", help="Pause strategy/manual trading.")
    sub.add_parser("resume", help="Resume trading after pause.")
    sub.add_parser("kill-switch", help="Enable persistent emergency stop.")
    sub.add_parser("clear-kill-switch", help="Clear persistent emergency stop.")
    manual = sub.add_parser("manual-order", help="Submit a risk-checked manual market order.")
    manual.add_argument("--symbol", required=True, help="Example: BTC/USDT")
    manual.add_argument("--side", required=True, choices=["buy", "sell"])
    manual.add_argument("--quote-qty", type=float, default=None, help="Quote amount for buys.")
    manual.add_argument(
        "--confirm",
        default="",
        help="Live manual orders require EXECUTE_REAL_ORDER.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)
    cfg = load_config(args.config)

    if args.command == "init-db":
        app = TradingApp(cfg)
        app.init_db()
        print(f"Initialized database: {cfg.resolve_path(cfg.database.path)}")
        return 0
    if args.command == "run-once":
        app = TradingApp(cfg)
        report = app.run_once()
        print(f"Run complete. Obsidian dashboard: {report}")
        return 0
    if args.command == "schedule":
        run_scheduler(cfg)
        return 0
    if args.command == "dashboard":
        return _run_dashboard(args.config)
    if args.command == "backtest":
        from vibe_trader.strategy.backtest import SimpleBacktester

        path = SimpleBacktester(cfg).run()
        print(f"Backtest summary: {path}")
        return 0
    if args.command == "performance":
        _print_performance(cfg)
        return 0
    if args.command == "doctor":
        return _doctor(cfg)
    if args.command in {"pause", "resume", "kill-switch", "clear-kill-switch"}:
        app = TradingApp(cfg)
        if args.command == "pause":
            app.set_paused(True)
            print("Trading paused.")
        elif args.command == "resume":
            app.set_paused(False)
            print("Trading resumed.")
        elif args.command == "kill-switch":
            app.set_kill_switch(True)
            print("Kill switch enabled.")
        else:
            app.set_kill_switch(False)
            print("Kill switch cleared.")
        return 0
    if args.command == "manual-order":
        app = TradingApp(cfg)
        result = app.execute_manual_order(
            symbol=args.symbol,
            side=args.side,
            quote_qty=args.quote_qty,
            confirmation_text=args.confirm,
        )
        print(result)
        return 0
    raise ValueError(args.command)


def _print_performance(cfg) -> None:
    repo = SQLiteRepository(cfg)
    repo.init_db()
    summary = summarize_performance(
        repo.list_recent_orders(500),
        repo.equity_curve(30),
        cfg.portfolio.initial_cash,
    )
    profit_factor = "inf"
    if summary.profit_factor != float("inf"):
        profit_factor = f"{summary.profit_factor:.2f}"
    print("Performance Summary")
    print(f"- status: {summary.status_label}")
    print(f"- filled orders: {summary.filled_orders}/{summary.total_orders}")
    print(f"- closed trades: {summary.closed_trades}")
    print(f"- win rate: {summary.win_rate:.1%}")
    print(f"- realized pnl: {summary.realized_pnl:.2f} {cfg.portfolio.quote_currency}")
    print(f"- fees: {summary.fees:.4f} {cfg.portfolio.quote_currency}")
    print(f"- profit factor: {profit_factor}")
    print(f"- return: {summary.return_pct:.2%}")
    print(f"- max drawdown: {summary.max_drawdown_pct:.2%}")
    print(f"- current drawdown: {summary.current_drawdown_pct:.2%}")


def _run_dashboard(config_path: str) -> int:
    dashboard_path = Path(__file__).parent / "dashboard" / "streamlit_app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(dashboard_path),
        "--",
        "--config",
        config_path,
    ]
    return subprocess.call(cmd)


def _doctor(cfg) -> int:
    problems: list[str] = []
    env_path = cfg.root_dir / ".env"
    gitignore = cfg.root_dir / ".gitignore"
    if env_path.exists() and gitignore.exists():
        if ".env" not in gitignore.read_text(encoding="utf-8"):
            problems.append(".gitignore does not ignore .env")
    if cfg.trading_mode in {"sandbox", "live"}:
        prefix = cfg.exchange.name.upper()
        if not os.getenv(f"{prefix}_API_KEY") or not os.getenv(f"{prefix}_SECRET"):
            problems.append(f"missing {prefix}_API_KEY/{prefix}_SECRET")
    if cfg.trading_mode == "live":
        if cfg.exchange.sandbox:
            problems.append("live mode requires exchange.sandbox=false")
        if not cfg.risk.allow_live_trading:
            problems.append("live mode requires risk.allow_live_trading=true")
        if os.getenv("LIVE_TRADING_ACK", "").lower() != "true":
            problems.append("LIVE_TRADING_ACK must be true")
        required_text = "I_UNDERSTAND_REAL_MONEY_RISK"
        if os.getenv("LIVE_TRADING_CONFIRM_TEXT") != required_text:
            problems.append(f"LIVE_TRADING_CONFIRM_TEXT must be {required_text}")
        max_live_equity = float(os.getenv("MAX_LIVE_EQUITY", "0") or 0)
        if max_live_equity <= 0:
            problems.append("MAX_LIVE_EQUITY must be > 0")
    print(f"Project root: {cfg.root_dir}")
    print(f"Mode: {cfg.trading_mode}")
    print(f"Database: {cfg.resolve_path(cfg.database.path)}")
    print(f"Obsidian dashboard: {cfg.resolve_path(cfg.reporting.dashboard_file)}")
    if problems:
        print("Doctor found issues:")
        for item in problems:
            print(f"- {item}")
        return 1
    print("Doctor checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
