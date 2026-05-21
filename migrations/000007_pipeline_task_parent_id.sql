ALTER TABLE pipeline_task_runs
    ADD COLUMN IF NOT EXISTS parent_task_id TEXT;

CREATE INDEX IF NOT EXISTS idx_pipeline_task_runs_parent_task_id
    ON pipeline_task_runs(parent_task_id);
