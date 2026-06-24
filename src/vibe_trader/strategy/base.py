from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from vibe_trader.models import Position, TradingSignal


class Strategy(ABC):
    @abstractmethod
    def generate(
        self,
        run_id: str,
        symbol: str,
        frames: dict[str, pd.DataFrame],
        position: Position | None,
    ) -> TradingSignal:
        raise NotImplementedError
