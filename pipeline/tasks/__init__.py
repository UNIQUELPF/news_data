"""Celery task modules for the news pipeline."""

from pipeline.tasks import backfill, crawl, embed, translate  # noqa: F401
