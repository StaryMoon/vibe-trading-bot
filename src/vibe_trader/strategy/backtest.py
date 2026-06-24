from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from vibe_trader.config.schema import AppConfig
from vibe_trader.data.exchange_client import ExchangeClient
from vibe_trader.indicators.technicals import add_indicators
from vibe_trader.models import Position
from vibe_trader.strategy.factory import create_strategy


class SimpleBacktester:
    """Small smoke-test backtester sharing the production strategy code."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.client = ExchangeClient(config)
        self.strategy = create_strategy(config)

    def run(self) -> Path:
        rows = [self._run_symbol(symbol) for symbol in self.config.exchange.symbols]
        out = self.config.root_dir / "reports" / "backtest_summary.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self._render(rows), encoding="utf-8")
        return out

    def _run_symbol(self, symbol: str) -> dict:
        frames = {
            timeframe: add_indicators(
                self.client.fetch_ohlcv(symbol, timeframe, self.config.exchange.ohlcv_limit),
                self.config.strategy,
            )
            for timeframe in self.config.exchange.timeframes
        }
        cash = self.config.portfolio.initial_cash / len(self.config.exchange.symbols)
        position: Position | None = None
        trades: list[float] = []
        equity_curve: list[float] = []

        base_frame = frames["15m"]
        for ts, row in base_frame.iloc[60:].iterrows():
            sliced = {
                timeframe: frame.loc[frame.index <= ts]
                for timeframe, frame in frames.items()
            }
            if not all(len(frame.dropna()) for frame in sliced.values()):
                continue
            price = float(row["close"])
            if position:
                position = replace(
                    position,
                    mark_price=price,
                    unrealized_pnl=(price - position.entry_price) * position.qty,
                )
            signal = self.strategy.generate("backtest", symbol, sliced, position)
            if signal.action == "BUY" and position is None:
                quote = min(
                    cash * self.config.execution.quote_order_size_pct,
                    self.config.execution.max_order_quote,
                )
                if quote > self.config.risk.min_quote_balance:
                    fill = price * (1 + self.config.execution.slippage_bps / 10_000)
                    fee = quote * self.config.execution.fee_bps / 10_000
                    qty = quote / fill
                    cash -= quote + fee
                    position = Position(
                        symbol=symbol,
                        side="long",
                        qty=qty,
                        entry_price=fill,
                        mark_price=fill,
                        stop_loss=fill * (1 - self.config.strategy.stop_loss_pct),
                        take_profit=fill * (1 + self.config.strategy.take_profit_pct),
                    )
            elif signal.action == "EXIT" and position is not None:
                fill = price * (1 - self.config.execution.slippage_bps / 10_000)
                gross = fill * position.qty
                fee = gross * self.config.execution.fee_bps / 10_000
                pnl = (fill - position.entry_price) * position.qty - fee
                cash += gross - fee
                trades.append(pnl)
                position = None

            mark_value = position.qty * price if position else 0.0
            equity_curve.append(cash + mark_value)

        if position:
            final_price = float(base_frame.iloc[-1]["close"])
            equity_curve.append(cash + position.qty * final_price)

        ending_equity = equity_curve[-1] if equity_curve else cash
        max_drawdown = self._max_drawdown(equity_curve)
        wins = [p for p in trades if p > 0]
        return {
            "symbol": symbol,
            "trades": len(trades),
            "wins": len(wins),
            "realized_pnl": sum(trades),
            "ending_equity": ending_equity,
            "max_drawdown": max_drawdown,
        }

    def _max_drawdown(self, curve: list[float]) -> float:
        peak = 0.0
        max_dd = 0.0
        for value in curve:
            peak = max(peak, value)
            if peak > 0:
                max_dd = min(max_dd, value / peak - 1)
        return max_dd

    def _render(self, rows: list[dict]) -> str:
        lines = [
            "# Backtest Summary",
            "",
            "> Smoke backtest. Treat this as engineering validation, not proof of edge.",
            "",
            "| Symbol | Trades | Win Rate | Realized PnL | Ending Equity | Max Drawdown |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for row in rows:
            win_rate = row["wins"] / row["trades"] if row["trades"] else 0.0
            lines.append(
                f"| {row['symbol']} | {row['trades']} | {win_rate:.1%} | "
                f"{row['realized_pnl']:.2f} | {row['ending_equity']:.2f} | "
                f"{row['max_drawdown']:.2%} |"
            )
        lines.extend(
            [
                "",
                "## Notes",
                "",
                "- Includes configured slippage and fee assumptions.",
                "- Uses the same rule strategy as the runtime loop.",
                "- Does not justify live trading; sandbox validation is still required.",
            ]
        )
        return "\n".join(lines)
