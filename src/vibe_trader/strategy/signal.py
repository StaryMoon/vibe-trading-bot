from __future__ import annotations

from typing import Any

import pandas as pd


def compact_snapshot(row: pd.Series) -> dict[str, Any]:
    keys = [
        "close",
        "rsi",
        "macd",
        "macd_signal",
        "macd_hist",
        "atr_pct",
        "volume_ratio",
        "realized_volatility",
    ]
    snapshot: dict[str, Any] = {}
    for key in keys:
        if key in row and pd.notna(row[key]):
            snapshot[key] = round(float(row[key]), 6)
    for key in row.index:
        if key.startswith("ma") and pd.notna(row[key]):
            snapshot[key] = round(float(row[key]), 6)
    return snapshot
