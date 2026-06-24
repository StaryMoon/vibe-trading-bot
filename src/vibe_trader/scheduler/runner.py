from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from vibe_trader.app import TradingApp
from vibe_trader.config.schema import AppConfig

logger = logging.getLogger(__name__)


def run_scheduler(config: AppConfig) -> None:
    app = TradingApp(config)
    scheduler = BlockingScheduler(timezone=config.project.timezone)

    def job() -> None:
        try:
            report = app.run_once()
            logger.info("cycle complete: %s", report)
        except Exception:
            logger.exception("scheduled cycle failed")

    scheduler.add_job(
        job,
        "interval",
        minutes=config.schedule.interval_minutes,
        id="vibe_trader_cycle",
        max_instances=1,
        coalesce=True,
        next_run_time=None,
    )
    logger.info("scheduler started; interval=%s minutes", config.schedule.interval_minutes)
    job()
    scheduler.start()
