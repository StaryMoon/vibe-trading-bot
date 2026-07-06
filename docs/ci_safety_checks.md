# CI Safety Checks

The GitHub Actions workflow is intentionally limited to local validation:

- It installs the package with development dependencies.
- It runs the unit test suite with synthetic market data and paper-trading paths.
- It runs `ruff check .` for import, syntax, and lint hygiene.
- It does not read `.env`.
- It does not require exchange API keys.
- It does not call live trading configs.
- It does not place orders.

This keeps CI useful for open-source review without turning a public workflow into a trading surface.

Local equivalent:

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check .
```

The tests cover the core risk and accounting paths that should not regress before any sandbox or live trial:

- strategy signal generation
- risk engine gates
- order lifecycle
- manual paper execution
- live execution confirmation gates
- Obsidian report generation
- realized PnL and drawdown metrics
