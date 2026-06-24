from __future__ import annotations

from abc import ABC, abstractmethod

from vibe_trader.config.schema import AppConfig
from vibe_trader.data.exchange_client import ExchangeClient
from vibe_trader.data.repository import SQLiteRepository
from vibe_trader.execution.live_spot import LiveSpotGateway
from vibe_trader.execution.paper_broker import PaperBroker
from vibe_trader.execution.sandbox_binance import SandboxGateway
from vibe_trader.models import OrderIntent, OrderResult, PortfolioState


class ExecutionGateway(ABC):
    @abstractmethod
    def place_order(
        self, intent: OrderIntent, state: PortfolioState
    ) -> tuple[OrderResult, PortfolioState]:
        raise NotImplementedError


def create_gateway(
    config: AppConfig,
    repo: SQLiteRepository,
    client: ExchangeClient,
) -> ExecutionGateway:
    if config.trading_mode == "paper":
        return PaperBroker(config, repo)
    if config.trading_mode == "sandbox":
        return SandboxGateway(config, repo, client)
    if config.trading_mode == "live":
        return LiveSpotGateway(config, repo, client)
    raise RuntimeError(f"unsupported trading mode: {config.trading_mode}")
