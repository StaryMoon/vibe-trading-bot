from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().isoformat()


def floor_timestamp(ts: pd.Timestamp, timeframe: str) -> pd.Timestamp:
    mapping = {"15m": "15min", "1h": "1h", "4h": "4h", "1d": "1D"}
    return ts.floor(mapping.get(timeframe, timeframe))
