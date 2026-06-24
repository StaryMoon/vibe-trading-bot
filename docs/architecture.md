# Architecture

The bot is built as a conservative event loop:

1. Load config and environment.
2. Fetch market candles.
3. Store candles in SQLite.
4. Compute indicators.
5. Generate rule-based signals.
6. Reconcile local and exchange state.
7. Run risk checks.
8. Execute only if approved.
9. Store orders and positions.
10. Generate Obsidian and dashboard data.

The LLM layer is outside the execution path. It reads stored facts and writes review text only.

The dashboard and CLI can execute actions, but all executable paths share the same gates:
pause/kill switch, data quality, reconciliation, risk engine, and audited order storage.

## Subsystems

- `data`: exchange client, synthetic data, SQLite repository.
- `indicators`: MA, RSI, MACD, ATR, volatility, volume ratio.
- `strategy`: multi-timeframe trend/momentum rule strategy.
- `risk`: pre-trade approval and pause rules.
- `execution`: paper broker, sandbox gateway, and gated live spot gateway.
- `portfolio`: local accounting and reconciliation.
- `reporting`: Obsidian Markdown.
- `dashboard`: executable Streamlit control app.
- `ai`: local/OpenAI review abstraction.
