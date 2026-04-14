ALTER TABLE pipeline_task_runs
    ADD COLUMN IF NOT EXISTS requested_by TEXT,
    ADD COLUMN IF NOT EXISTS request_ip TEXT,
    ADD COLUMN IF NOT EXISTS user_agent TEXT;

CREATE INDEX IF NOT EXISTS idx_pipeline_task_runs_requested_by
    ON pipeline_task_runs(requested_by);
