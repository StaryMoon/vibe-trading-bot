# Changelog

## 0.2.2

- Added GitHub Actions CI for Python 3.11 and 3.12.
- Added README CI badge.
- Documented CI safety boundaries for synthetic data, paper trading, and live-key isolation.

## 0.2.1

- Added shared performance analytics for orders and equity curves.
- Added `vibe-trader performance` CLI command.
- Added performance summary to the Obsidian dashboard.
- Added performance metric cards to the Streamlit dashboard.
- Added unit tests for realized PnL, win rate, profit factor, and drawdown.

## 0.2.0

- Added gated live spot execution gateway.
- Added manual order command and dashboard controls.
- Added pause, resume, kill switch, and clear kill switch.
- Added small-capital Binance live spot config template.
- Added quote-cost market buy support for Binance via CCXT.
- Added tests for live gates and manual paper execution.

## 0.1.0

- Initial MVP scaffold.
- Local synthetic paper trading.
- Binance sandbox gateway skeleton.
- SQLite audit trail.
- Rule-based BTC/ETH strategy.
- Risk engine.
- Obsidian Markdown reports.
- Read-only Streamlit dashboard.
- Local/OpenAI review abstraction.
- Basic pytest coverage.
