"""APScheduler-based daily pipeline scheduler."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_pipeline_job() -> None:
    """Job that triggers the pipeline run (reuses server-level runner)."""
    from .server import trigger_pipeline

    from datetime import date

    today = date.today().isoformat()
    logger.info("Scheduler triggered pipeline for %s", today)
    trigger_pipeline(today)


def start_scheduler() -> None:
    """Start the scheduler if enabled in settings."""
    global _scheduler
    if not settings.scheduler_enabled:
        logger.info("Scheduler is disabled")
        return

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _run_pipeline_job,
        CronTrigger(
            hour=settings.scheduler_cron_hour,
            minute=settings.scheduler_cron_minute,
            timezone=settings.scheduler_timezone,
        ),
        id="daily_pipeline",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started: %02d:%02d %s",
        settings.scheduler_cron_hour,
        settings.scheduler_cron_minute,
        settings.scheduler_timezone,
    )


def stop_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
