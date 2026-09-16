"""Celery application: scheduled daily/monthly monitoring jobs.

Every scheduled job is idempotent: it records a `JobRun` row keyed by
(job_name, run_key) inside a DB-unique constraint before doing work, so a
retried or duplicated trigger for the same day/month is a no-op.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "controlflow",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.monitoring"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "daily-monitoring": {
        "task": "app.tasks.monitoring.run_daily_monitoring",
        "schedule": crontab(hour=2, minute=0),
    },
    "monthly-review": {
        "task": "app.tasks.monitoring.run_monthly_review",
        "schedule": crontab(hour=3, minute=0, day_of_month=1),
    },
}
