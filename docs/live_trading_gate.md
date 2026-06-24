# Live Trading Gate

Live trading is available only through explicit small-capital spot gates. Before use, all items below must be true.

## Required Evidence

- At least 30 calendar days of stable sandbox operation.
- No duplicate-order incidents.
- No unhandled order timeout incidents.
- Local and exchange reconciliation passes consistently.
- Every order has signal reason, risk decision, order id, fill info, and fee.
- Data anomaly tests pause trading.
- API/network failure tests pause trading.
- Database-lock or process-restart tests do not duplicate orders.
- Unit tests pass.
- A manual review confirms max position, max daily loss, and cooldown settings.
- `vibe-trader --config configs/live_binance_spot_small.yaml doctor` passes.
- `LIVE_TRADING_ACK=true`.
- `LIVE_TRADING_CONFIRM_TEXT=I_UNDERSTAND_REAL_MONEY_RISK`.
- `MAX_LIVE_EQUITY` is set to the exact maximum capital you are willing to expose.

## API Key Rules

- No withdrawal permission.
- IP restriction if the exchange supports it.
- Dedicated small-capital subaccount if possible.
- Key stored only in `.env` or local environment variables.

## Capital Rules

- Start with small spot-only capital.
- No leverage.
- No shorting.
- No compounding after early wins.
- Stop immediately after unexpected behavior.
- Prefer manual `manual-order` tests before scheduled `run-once`.
