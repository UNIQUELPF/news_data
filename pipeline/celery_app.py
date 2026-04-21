import os

from celery import Celery, Task

from pipeline.task_state import classify_task_type, record_pipeline_task, sync_pipeline_task_state


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


celery_app = Celery(
    "news_pipeline",
    broker=_env("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=_env("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)


# Legacy PipelineTrackedTask is disabled to align with V2 architecture.
# Native Celery status management will be used instead.
class PipelineTrackedTask(Task):
    pass


celery_app.Task = PipelineTrackedTask

celery_app.conf.update(
    timezone=_env("TZ", "Asia/Shanghai"),
    enable_utc=False,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_routes={
        "pipeline.tasks.backfill.*": {"queue": "translate"},
        "pipeline.tasks.crawl.*": {"queue": "crawl"},
        "pipeline.tasks.translate.*": {"queue": "translate"},
        "pipeline.tasks.embed.*": {"queue": "embed"},
    },
    beat_scheduler='celery_sqlalchemy_scheduler.schedulers:DatabaseScheduler',
    beat_dburi=f"postgresql://{_env('POSTGRES_USER', 'your_user')}:{_env('POSTGRES_PASSWORD', 'your_password')}@{_env('POSTGRES_HOST', 'postgres')}:{_env('POSTGRES_PORT', '5432')}/{_env('POSTGRES_DB', 'scrapy_db')}",
)

celery_app.autodiscover_tasks(["pipeline.tasks"])
