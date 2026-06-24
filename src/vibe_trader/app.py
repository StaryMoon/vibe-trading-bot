from __future__ import annotations

import logging
import uuid
from dataclasses import replace
from datetime import UTC, date, datetime

from vibe_trader.ai.reviewer import DailyReviewer
from vibe_trader.config.schema import AppConfig
from vibe_trader.data.exchange_client import ExchangeClient
from vibe_trader.data.market_data import DataQualityReport, MarketDataService
from vibe_trader.data.repository import SQLiteRepository
from vibe_trader.execution.gateway import create_gateway
from vibe_trader.portfolio.accounting import PortfolioService
from vibe_trader.portfolio.reconciliation import ReconciliationService
from vibe_trader.reporting.obsidian import ObsidianReporter
from vibe_trader.risk.engine import RiskEngine
from vibe_trader.strategy.factory import create_strategy

logger = logging.getLogger(__name__)


class TradingApp:
    def __init__(self, config: AppConfig):
        self.config = config
        self.repo = SQLiteRepository(config)
        self.client = ExchangeClient(config)
        self.market = MarketDataService(config, self.repo, self.client)
        self.portfolio = PortfolioService(config, self.repo, self.client)
        self.reconciliation = ReconciliationService(config, self.client)
        self.strategy = create_strategy(config)
        self.risk = RiskEngine(config, self.repo)
        self.gateway = create_gateway(config, self.repo, self.client)
        self.reporter = ObsidianReporter(config, self.repo)
        self.reviewer = DailyReviewer(config, self.repo)

    def init_db(self) -> None:
        self.repo.init_db()

    def run_once(self) -> str:
        run_id = str(uuid.uuid4())
        self.repo.init_db()
        self.repo.start_run(run_id)
        try:
            if self._trading_blocked(run_id):
                review = self.reviewer.generate()
                self.repo.save_review(date.today().isoformat(), review)
                report_path = self.reporter.render()
                self.repo.finish_run(run_id, "PAUSED", f"report={report_path}")
                return str(report_path)

            frames = self.market.refresh()
            prices = self.market.latest_prices(frames)
            state = self.portfolio.load_state(prices)
            self.portfolio.save_snapshot(state, {"run_id": run_id, "phase": "pre_signal"})
            reconciliation = self.reconciliation.check(state)

            for symbol in self.config.exchange.symbols:
                if symbol in state.positions:
                    state = replace(
                        state,
                        positions={
                            **state.positions,
                            symbol: replace(state.positions[symbol], mark_price=prices[symbol]),
                        },
                    )
                quality = self._quality_for_symbol(symbol, frames)
                signal = self.strategy.generate(
                    run_id=run_id,
                    symbol=symbol,
                    frames=frames[symbol],
                    position=state.positions.get(symbol),
                )
                self.repo.insert_signal(signal)
                decision = self.risk.evaluate(
                    signal=signal,
                    state=state,
                    data_quality=quality,
                    reconciliation=reconciliation,
                    price=prices[symbol],
                )
                self.repo.insert_risk_event(
                    run_id=run_id,
                    symbol=symbol,
                    rule="risk_engine",
                    status=decision.status,
                    message=decision.message,
                    details=decision.details,
                )
                if decision.approved and decision.order_intent:
                    order, state = self.gateway.place_order(decision.order_intent, state)
                    logger.info("order %s %s %s", order.symbol, order.side, order.status)

            review = self.reviewer.generate()
            self.repo.save_review(date.today().isoformat(), review)
            report_path = self.reporter.render()
            self.repo.finish_run(run_id, "OK", f"report={report_path}")
            return str(report_path)
        except Exception as exc:
            logger.exception("run failed")
            self.repo.insert_risk_event(run_id, None, "runtime", "FAILED", str(exc))
            self.repo.finish_run(run_id, "FAILED", str(exc))
            raise

    def _quality_for_symbol(
        self, symbol: str, frames: dict[str, dict]
    ) -> DataQualityReport:
        frame = frames[symbol].get("15m")
        if frame is None:
            return DataQualityReport(False, "missing 15m frame")
        return self.market.check_quality(symbol, frame)

    def execute_manual_order(
        self,
        symbol: str,
        side: str,
        quote_qty: float | None = None,
        confirmation_text: str = "",
    ) -> str:
        run_id = str(uuid.uuid4())
        self.repo.init_db()
        self.repo.start_run(run_id)
        try:
            if self._trading_blocked(run_id):
                self.repo.finish_run(run_id, "PAUSED", "manual order blocked by control state")
                return "manual order blocked by pause/kill switch"
            if self.config.trading_mode == "live" and confirmation_text != "EXECUTE_REAL_ORDER":
                message = "manual live order requires confirmation text EXECUTE_REAL_ORDER"
                self.repo.insert_risk_event(
                    run_id, symbol, "manual_order", "REJECTED_CONFIRM", message
                )
                self.repo.finish_run(run_id, "REJECTED", message)
                return message

            frames = self.market.refresh()
            prices = self.market.latest_prices(frames)
            state = self.portfolio.load_state(prices)
            reconciliation = self.reconciliation.check(state)
            quality = self._quality_for_symbol(symbol, frames)
            action = "BUY" if side.lower() == "buy" else "EXIT"
            signal = self._manual_signal(run_id, symbol, action, quote_qty)
            self.repo.insert_signal(signal)
            decision = self.risk.evaluate(
                signal=signal,
                state=state,
                data_quality=quality,
                reconciliation=reconciliation,
                price=prices[symbol],
                quote_override=quote_qty,
            )
            self.repo.insert_risk_event(
                run_id,
                symbol,
                "manual_order_risk",
                decision.status,
                decision.message,
                decision.details,
            )
            if not decision.approved or decision.order_intent is None:
                self.repo.finish_run(run_id, "REJECTED", decision.message)
                self._save_review()
                self.reporter.render()
                return f"{decision.status}: {decision.message}"

            order, state = self.gateway.place_order(decision.order_intent, state)
            self.portfolio.save_snapshot(state, {"manual_order": order.exchange_order_id})
            self.repo.finish_run(run_id, order.status.upper(), order.message)
            self._save_review()
            self.reporter.render()
            return f"{order.status}: {order.symbol} {order.side} {order.filled_qty:.8f}"
        except Exception as exc:
            logger.exception("manual order failed")
            self.repo.insert_risk_event(run_id, symbol, "manual_order", "FAILED", str(exc))
            self.repo.finish_run(run_id, "FAILED", str(exc))
            self._save_review()
            self.reporter.render()
            raise

    def set_paused(self, paused: bool) -> None:
        self.repo.init_db()
        self.repo.set_control("paused", paused)

    def set_kill_switch(self, enabled: bool) -> None:
        self.repo.init_db()
        self.repo.set_control("kill_switch", enabled)

    def _trading_blocked(self, run_id: str) -> bool:
        control = self.repo.get_control()
        if control.get("kill_switch") == "true":
            self.repo.insert_risk_event(
                run_id,
                None,
                "control",
                "PAUSED_KILL_SWITCH",
                "kill switch is enabled",
            )
            return True
        if control.get("paused") == "true":
            self.repo.insert_risk_event(run_id, None, "control", "PAUSED", "bot is paused")
            return True
        return False

    def _manual_signal(
        self, run_id: str, symbol: str, action: str, quote_qty: float | None
    ):
        from vibe_trader.models import TradingSignal

        reason = f"manual dashboard {action.lower()}"
        if quote_qty:
            reason += f" for {quote_qty:.2f} {self.config.portfolio.quote_currency}"
        return TradingSignal(
            run_id=run_id,
            symbol=symbol,
            action=action,  # type: ignore[arg-type]
            confidence=1.0,
            reason=reason,
            details={"source": "dashboard", "created_at": datetime.now(UTC).isoformat()},
        )

    def _save_review(self) -> None:
        review = self.reviewer.generate()
        self.repo.save_review(date.today().isoformat(), review)
