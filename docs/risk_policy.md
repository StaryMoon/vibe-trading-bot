# Risk Policy

The project is designed to stop trading when uncertain.

## Default Safety

- Default config is paper mode.
- Live execution requires explicit config and environment gates.
- `.env` and local databases are ignored by Git.
- Sandbox keys and production keys must be separated.

## Pre-Trade Gates

Every order intent must pass:

- Data quality check.
- Local/exchange reconciliation.
- Duplicate order check.
- Cooldown check.
- Daily loss check.
- Consecutive loss check.
- Symbol exposure limit.
- Total exposure limit.
- Single-trade loss budget.
- Cash reserve check.
- Persistent pause / kill switch check.

## AI Boundary

AI can:

- Explain trades.
- Summarize daily behavior.
- Summarize bugs and anomalies.
- Propose parameter ideas.

AI cannot:

- Place orders.
- Modify live config automatically.
- Disable risk checks.
- Approve live trading.
