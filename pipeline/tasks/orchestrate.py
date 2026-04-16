from pipeline.celery_app import celery_app
import logging
from croniter import croniter

logger = logging.getLogger(__name__)



@celery_app.task(name="pipeline.tasks.orchestrate.dispatch_periodic_tasks", bind=True)
def dispatch_periodic_tasks(self):
    """Dispatch periodic tasks based on cron expressions.
    
    This task runs periodically (e.g., every minute) and checks which scheduled
    tasks should run based on their cron expressions and last run time.
    
    Returns:
        dict: Summary of dispatched tasks
    """
    from datetime import datetime, timedelta
    from pipeline.db import get_db_connection
    
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, name, task_path, cron_expr, params, last_run_at 
            FROM pipeline_periodic_tasks 
            WHERE is_enabled = true
        """)
        tasks = cursor.fetchall()

        # Use Asia/Shanghai timezone (UTC+8)
        # Note: We use naive datetime but ensure we're comparing in local time
        # In production, consider using timezone-aware datetime with pytz
        now = datetime.now()
        dispatched_ids = []
        
        # Maximum lookback period to avoid infinite loops (7 days)
        max_lookback_days = 7
        max_lookback_minutes = max_lookback_days * 24 * 60

        for task_id, name, task_path, cron_expr, params, last_run_at in tasks:
            cron_expr = str(cron_expr).strip()
            if not cron_expr:
                logger.warning(f"Empty cron expression for task {name} (id: {task_id})")
                continue
            
            try:
                # Use croniter to check if the task is due
                # If never run, look back 60 minutes
                base_time = last_run_at if last_run_at else (now - timedelta(minutes=60))
                
                # get_next returns the first occurrence strictly after base_time
                it = croniter(cron_expr, base_time)
                should_run = it.get_next(datetime) <= now
                
            except Exception as e:
                logger.error(f"Invalid cron expression '{cron_expr}' for task {name}: {e}")
                continue

            if should_run:
                try:
                    celery_app.send_task(task_path, kwargs=params)
                    dispatched_ids.append(task_id)
                    logger.info(
                        "Dispatched periodic task [%s] (cron: %s)",
                        name, cron_expr
                    )
                except Exception as e:
                    logger.error(f"Failed to dispatch task {name}: {e}")
            else:
                logger.debug(
                    "Periodic check [%s]: cron=%s, last_run=%s, no match in checked period",
                    name, cron_expr, last_run_at.strftime('%Y-%m-%d %H:%M') if last_run_at else "never"
                )

        if dispatched_ids:
            cursor.execute(
                "UPDATE pipeline_periodic_tasks SET last_run_at = CURRENT_TIMESTAMP WHERE id = ANY(%s)",
                (dispatched_ids,)
            )
            connection.commit()

        return {
            "dispatched_count": len(dispatched_ids),
            "dispatched_task_ids": dispatched_ids,
            "checked_at": now.isoformat()
        }
    except Exception as e:
        connection.rollback()
        logger.error(f"Error in dispatch_periodic_tasks: {e}")
        raise
    finally:
        connection.close()
