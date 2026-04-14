import json

from pipeline.db import get_db_connection


def ensure_pipeline_task_runs_table():
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_task_runs (
                id BIGSERIAL PRIMARY KEY,
                task_id TEXT NOT NULL UNIQUE,
                task_name TEXT NOT NULL,
                task_type TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'PENDING',
                params JSONB,
                result JSONB,
                error_message TEXT,
                requested_by TEXT,
                request_ip TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute("ALTER TABLE pipeline_task_runs ADD COLUMN IF NOT EXISTS requested_by TEXT")
        cursor.execute("ALTER TABLE pipeline_task_runs ADD COLUMN IF NOT EXISTS request_ip TEXT")
        cursor.execute("ALTER TABLE pipeline_task_runs ADD COLUMN IF NOT EXISTS user_agent TEXT")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_task_runs_task_type ON pipeline_task_runs(task_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_task_runs_state ON pipeline_task_runs(state)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_task_runs_created_at ON pipeline_task_runs(created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_task_runs_requested_by ON pipeline_task_runs(requested_by)")
        
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_periodic_tasks (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                task_path TEXT NOT NULL,
                cron_expr TEXT NOT NULL,
                params JSONB NOT NULL DEFAULT '{}',
                is_enabled BOOLEAN NOT NULL DEFAULT true,
                last_run_at TIMESTAMP
            )
            """
        )
        # Setup initial seeds with UPSERT to handle renames
        cursor.execute("SELECT count(*) FROM pipeline_periodic_tasks")
        
        # Cleanup old names that are now deprecated
        cursor.execute(
            """
            DELETE FROM pipeline_periodic_tasks 
            WHERE name IN ('优先级爬虫(每30分钟)', '后台翻译碎屑(每分钟)', '后台向量碎屑(每分钟)')
            """
        )
        
        cursor.execute(
            """
            INSERT INTO pipeline_periodic_tasks (name, task_path, cron_expr, params) VALUES
            ('全量爬虫巡航 (Crawler Auto-Cruise)', 'pipeline.tasks.crawl.run_all_spiders_automatic', '*/30 * * * *', '{}'::jsonb),
            ('后台自动翻译 (Auto Article Translation)', 'pipeline.tasks.translate.auto_translate_articles', '*/5 * * * *', '{"limit": 3}'::jsonb),
            ('后台自动向量 (Auto Article Embedding)', 'pipeline.tasks.embed.auto_embed_articles', '*/5 * * * *', '{"limit": 3}'::jsonb)
            ON CONFLICT (name) DO NOTHING
            """
        )
        connection.commit()
    finally:
        connection.close()


def classify_task_type(task_name: str) -> str:
    if task_name.startswith("pipeline.tasks.backfill."):
        return "backfill"
    if task_name.startswith("pipeline.tasks.orchestrate."):
        return "pipeline_run"
    if task_name.startswith("pipeline.tasks.translate."):
        return "translate"
    if task_name.startswith("pipeline.tasks.embed."):
        return "embed"
    if task_name.startswith("pipeline.tasks.crawl."):
        return "crawl"
    return "task"


def record_pipeline_task(
    task_id: str,
    task_name: str,
    task_type: str,
    params: dict,
    *,
    requested_by: str | None = None,
    request_ip: str | None = None,
    user_agent: str | None = None,
    state: str = "PENDING",
    parent_task_id: str | None = None,
):
    ensure_pipeline_task_runs_table()
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO pipeline_task_runs (
                task_id,
                task_name,
                task_type,
                state,
                params,
                parent_task_id,
                requested_by,
                request_ip,
                user_agent,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (task_id) DO UPDATE SET
                task_name = EXCLUDED.task_name,
                task_type = EXCLUDED.task_type,
                state = EXCLUDED.state,
                params = EXCLUDED.params,
                parent_task_id = COALESCE(pipeline_task_runs.parent_task_id, EXCLUDED.parent_task_id),
                requested_by = COALESCE(pipeline_task_runs.requested_by, EXCLUDED.requested_by),
                request_ip = COALESCE(pipeline_task_runs.request_ip, EXCLUDED.request_ip),
                user_agent = COALESCE(pipeline_task_runs.user_agent, EXCLUDED.user_agent),
                updated_at = CURRENT_TIMESTAMP
            """,
            (task_id, task_name, task_type, state, json.dumps(params), parent_task_id, requested_by, request_ip, user_agent),
        )
        connection.commit()
    finally:
        connection.close()


def sync_pipeline_task_state(task_id: str, state: str, result=None):
    ensure_pipeline_task_runs_table()
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        if result is None:
            result_json = None
        else:
            try:
                result_json = json.dumps(result)
            except TypeError:
                result_json = json.dumps({"repr": repr(result), "str": str(result)})
        error_message = None
        if state == "FAILURE" and result is not None:
            error_message = str(result)
        cursor.execute(
            """
            UPDATE pipeline_task_runs
            SET state = %s,
                result = COALESCE(%s::jsonb, result),
                error_message = COALESCE(%s, error_message),
                updated_at = CURRENT_TIMESTAMP
            WHERE task_id = %s
            """,
            (state, result_json, error_message, task_id),
        )
        connection.commit()
    finally:
        connection.close()


def append_pipeline_task_note(task_id: str, note: str):
    ensure_pipeline_task_runs_table()
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE pipeline_task_runs
            SET error_message = CASE
                    WHEN error_message IS NULL OR error_message = '' THEN %s
                    ELSE error_message || E'\n' || %s
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE task_id = %s
            """,
            (note, note, task_id),
        )
        connection.commit()
    finally:
        connection.close()
