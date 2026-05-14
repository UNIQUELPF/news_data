"""add missing tables and columns from sql scripts

Revision ID: 003_add_missing_tables
Revises: 002_add_sources_organization
Create Date: 2026-05-11 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "003_add_missing_tables"
down_revision: Union[str, None] = "002_add_sources_organization"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add legacy_table to sources and articles
    op.execute("ALTER TABLE sources ADD COLUMN IF NOT EXISTS legacy_table TEXT;")
    op.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS legacy_table TEXT;")

    # Add crawl_jobs
    op.execute("""
    CREATE TABLE IF NOT EXISTS crawl_jobs (
        id BIGSERIAL PRIMARY KEY,
        spider_name TEXT NOT NULL,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'running',
        items_scraped INTEGER NOT NULL DEFAULT 0,
        error_message TEXT
    );
    """)

    # Add crawl_errors
    op.execute("""
    CREATE TABLE IF NOT EXISTS crawl_errors (
        id BIGSERIAL PRIMARY KEY,
        spider_name TEXT NOT NULL,
        source_url TEXT,
        error_stage TEXT,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Add pipeline_task_runs
    op.execute("""
    CREATE TABLE IF NOT EXISTS pipeline_task_runs (
        id BIGSERIAL PRIMARY KEY,
        task_id TEXT NOT NULL UNIQUE,
        task_name TEXT NOT NULL,
        task_type TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'PENDING',
        params JSONB,
        result JSONB,
        error_message TEXT,
        parent_task_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_task_runs_task_type ON pipeline_task_runs(task_type);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_task_runs_state ON pipeline_task_runs(state);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_task_runs_created_at ON pipeline_task_runs(created_at DESC);")

    # Add audit columns to pipeline_task_runs
    op.execute("""
    ALTER TABLE pipeline_task_runs
        ADD COLUMN IF NOT EXISTS requested_by TEXT,
        ADD COLUMN IF NOT EXISTS request_ip TEXT,
        ADD COLUMN IF NOT EXISTS user_agent TEXT,
        ADD COLUMN IF NOT EXISTS parent_task_id TEXT;
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_task_runs_requested_by ON pipeline_task_runs(requested_by);")


def downgrade() -> None:
    # Optional: Implement downgrade logic, though usually not strictly required for local dev environments
    op.execute("DROP TABLE IF EXISTS crawl_jobs;")
    op.execute("DROP TABLE IF EXISTS crawl_errors;")
    op.execute("DROP TABLE IF EXISTS pipeline_task_runs;")
    op.execute("ALTER TABLE sources DROP COLUMN IF EXISTS legacy_table;")
    op.execute("ALTER TABLE articles DROP COLUMN IF EXISTS legacy_table;")
