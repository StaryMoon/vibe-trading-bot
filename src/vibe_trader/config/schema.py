from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

TradingMode = Literal["paper", "sandbox", "live"]


class ProjectConfig(BaseModel):
    name: str = "vibe-trading-bot"
    timezone: str = "Asia/Shanghai"


class DatabaseConfig(BaseModel):
    path: Path = Path("data/vibe_trader.sqlite3")


class ExchangeConfig(BaseModel):
    name: str = "synthetic"
    sandbox: bool = True
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    timeframes: list[str] = Field(default_factory=lambda: ["15m", "1h", "4h"])
    ohlcv_limit: int = 260
    synthetic_seed: int = 14789


class PortfolioConfig(BaseModel):
    initial_cash: float = 1000.0
    quote_currency: str = "USDT"


class StrategyConfig(BaseModel):
    name: str = "trend_rsi_macd"
    fast_ma: int = 20
    slow_ma: int = 50
    trend_ma: int = 200
    rsi_period: int = 14
    rsi_entry_min: float = 45
    rsi_entry_max: float = 72
    rsi_exit_min: float = 38
    atr_period: int = 14
    volume_ma: int = 20
    min_volume_ratio: float = 0.75
    stop_loss_pct: float = 0.015
    take_profit_pct: float = 0.03
    trailing_stop_pct: float = 0.018


class RiskConfig(BaseModel):
    max_symbol_exposure_pct: float = 0.20
    max_total_exposure_pct: float = 0.40
    max_single_trade_loss_pct: float = 0.005
    max_daily_loss_pct: float = 0.02
    cooldown_minutes: int = 60
    max_consecutive_losses: int = 3
    max_price_gap_pct: float = 0.08
    stale_candle_minutes: int = 45
    min_quote_balance: float = 10.0
    dust_base_qty: float = 0.000001
    require_reconciliation: bool = True
    allow_live_trading: bool = False


class ExecutionConfig(BaseModel):
    order_type: Literal["market"] = "market"
    quote_order_size_pct: float = 0.10
    max_order_quote: float = 100.0
    slippage_bps: float = 10
    fee_bps: float = 10


class ReportingConfig(BaseModel):
    obsidian_dir: Path = Path("reports/obsidian")
    dashboard_file: Path = Path("reports/obsidian/account_dashboard.md")


class ScheduleConfig(BaseModel):
    interval_minutes: int = 15


class AIConfig(BaseModel):
    provider: Literal["local", "openai"] = "local"
    model: str = ""


class AppConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    trading_mode: TradingMode = "paper"
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    portfolio: PortfolioConfig = Field(default_factory=PortfolioConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    root_dir: Path = Field(default=Path("."), exclude=True)

    @model_validator(mode="after")
    def validate_live_gate(self) -> AppConfig:
        if self.trading_mode == "live" and not self.risk.allow_live_trading:
            msg = "live mode requires risk.allow_live_trading=true and external env gates"
            raise ValueError(msg)
        return self

    def resolve_path(self, path: Path) -> Path:
        return path if path.is_absolute() else (self.root_dir / path).resolve()
