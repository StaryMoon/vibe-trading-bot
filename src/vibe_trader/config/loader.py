from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from vibe_trader.config.schema import AppConfig


def project_root_from_config(config_path: Path) -> Path:
    return config_path.resolve().parents[1]


def load_config(config_path: str | Path = "configs/default.yaml") -> AppConfig:
    path = Path(config_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    root_dir = project_root_from_config(path)
    load_dotenv(root_dir / ".env", override=False)

    raw: dict[str, Any] = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    env_mode = os.getenv("VIBE_TRADER_MODE")
    if env_mode:
        raw["trading_mode"] = env_mode

    env_db = os.getenv("VIBE_TRADER_DB_PATH")
    if env_db:
        raw.setdefault("database", {})["path"] = env_db

    env_ai = os.getenv("VIBE_TRADER_AI_PROVIDER")
    if env_ai:
        raw.setdefault("ai", {})["provider"] = env_ai

    cfg = AppConfig.model_validate(raw)
    cfg.root_dir = root_dir
    return cfg
