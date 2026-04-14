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


class PipelineTrackedTask(Task):
    def before_start(self, task_id, args, kwargs):
        parent_task_id = (kwargs or {}).get("parent_task_id")
        record_pipeline_task(
            task_id,
            self.name,
            classify_task_type(self.name),
            kwargs or {"args": list(args)},
            state="STARTED",
            parent_task_id=parent_task_id,
        )

    def on_success(self, retval, task_id, args, kwargs):
        sync_pipeline_task_state(task_id, "SUCCESS", retval)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        sync_pipeline_task_state(task_id, "FAILURE", exc)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        sync_pipeline_task_state(task_id, "RETRY", {"error": str(exc)})


celery_app.Task = PipelineTrackedTask

celery_app.conf.update(
    timezone=_env("TZ", "Asia/Shanghai"),
    enable_utc=False,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_routes={
        "pipeline.tasks.backfill.*": {"queue": "translate"},
        "pipeline.tasks.crawl.*": {"queue": "crawl"},
        "pipeline.tasks.orchestrate.*": {"queue": "crawl"},
        "pipeline.tasks.translate.*": {"queue": "translate"},
        "pipeline.tasks.embed.*": {"queue": "embed"},
    },
    beat_schedule={
        "dispatch-periodic-tasks-every-minute": {
            "task": "pipeline.tasks.orchestrate.dispatch_periodic_tasks",
            "schedule": 60.0,
        },
    },
)

celery_app.autodiscover_tasks(["pipeline.tasks"])
