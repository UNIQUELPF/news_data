CREATE TABLE IF NOT EXISTS pipeline_task_runs (
    id BIGSERIAL PRIMARY KEY,
    task_id TEXT NOT NULL UNIQUE,
    task_name TEXT NOT NULL,
    task_type TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'PENDING',
    params JSONB,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pipeline_task_runs_task_type ON pipeline_task_runs(task_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_task_runs_state ON pipeline_task_runs(state);
CREATE INDEX IF NOT EXISTS idx_pipeline_task_runs_created_at ON pipeline_task_runs(created_at DESC);
