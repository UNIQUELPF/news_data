from pipeline.celery_app import celery_app





def _match_cron_field(field_expr, value, max_val):
    """Check if a value matches a single cron field expression.
    Supports: * (any), */N (every N), N (exact), N,M (list), N-M (range).
    """
    for part in field_expr.split(','):
        part = part.strip()
        if part == '*':
            return True
        if '/' in part:
            base, step = part.split('/', 1)
            step = int(step)
            if base == '*':
                if value % step == 0:
                    return True
            else:
                base_val = int(base)
                if value >= base_val and (value - base_val) % step == 0:
                    return True
        elif '-' in part:
            lo, hi = part.split('-', 1)
            if int(lo) <= value <= int(hi):
                return True
        else:
            if value == int(part):
                return True
    return False


def _cron_matches(cron_expr, dt):
    """Check if a datetime matches a cron expression (minute hour dom month dow)."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False
    minute, hour, dom, month, dow = parts
    return (
        _match_cron_field(minute, dt.minute, 59) and
        _match_cron_field(hour, dt.hour, 23) and
        _match_cron_field(dom, dt.day, 31) and
        _match_cron_field(month, dt.month, 12) and
        _match_cron_field(dow, dt.isoweekday() % 7, 6)  # 0=Sunday
    )


@celery_app.task(name="pipeline.tasks.orchestrate.dispatch_periodic_tasks", bind=True)
def dispatch_periodic_tasks(self):
    from datetime import datetime, timedelta, timezone
    from pipeline.db import get_db_connection
    import logging

    logger = logging.getLogger(__name__)

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, name, task_path, cron_expr, params, last_run_at FROM pipeline_periodic_tasks WHERE is_enabled = true")
        tasks = cursor.fetchall()

        # Always use UTC+8 (Beijing time) regardless of container timezone
        now = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)
        dispatched_ids = []

        for task_id, name, task_path, cron_expr, params, last_run_at in tasks:
            cron_expr = str(cron_expr).strip()
            # If never run, treat as very old
            prev_run = last_run_at if last_run_at else (now - timedelta(days=365))

            # Walk minute-by-minute from (prev_run + 1 min) to now, checking for cron match.
            # Cap at 60 checks to avoid runaway loops on first-ever runs.
            check_start = prev_run.replace(second=0, microsecond=0) + timedelta(minutes=1)
            should_run = False
            for i in range(60):
                candidate = check_start + timedelta(minutes=i)
                if candidate > now:
                    break
                if _cron_matches(cron_expr, candidate):
                    should_run = True
                    break

            logger.info(
                "Periodic check [%s]: now=%s, last_run=%s, should_run=%s",
                name, now.strftime('%H:%M:%S'), prev_run.strftime('%H:%M:%S'), should_run
            )

            if should_run:
                celery_app.send_task(task_path, kwargs=params)
                dispatched_ids.append(task_id)

        if dispatched_ids:
            cursor.execute("UPDATE pipeline_periodic_tasks SET last_run_at = CURRENT_TIMESTAMP WHERE id = ANY(%s)", (dispatched_ids,))
            connection.commit()

        return {"dispatched_count": len(dispatched_ids), "dispatched_task_ids": dispatched_ids}
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        connection.close()
