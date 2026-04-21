import logging
import sys
from celery import Celery

from pipeline.celery_app import celery_app
from pipeline.task_state import record_pipeline_task, sync_pipeline_task_state, classify_task_type

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("celery_monitor")

def _ensure_task_exists(task_id, task_name=None, kwargs_str="{}"):
    """
    Since task-sent might not be caught if monitor is restarted, 
    we need to ensure the row exists before syncing state.
    """
    if not task_name:
        # Try to get from Celery AsyncResult if missing
        res = celery_app.AsyncResult(task_id)
        task_name = res.name or "unknown_task"
        
    record_pipeline_task(
        task_id=task_id,
        task_name=task_name,
        task_type=classify_task_type(task_name),
        params={},
        state="PENDING",
        requested_by="system_scheduler"
    )

def on_task_sent(event):
    task_id = event.get('uuid')
    task_name = event.get('name')
    if not task_name or not task_name.startswith('pipeline.tasks.'):
        return
        
    logger.info(f"Task sent: {task_name} [{task_id}]")
    _ensure_task_exists(task_id, task_name)

def on_task_received(event):
    task_id = event.get('uuid')
    task_name = event.get('name')
    if task_name and task_name.startswith('pipeline.tasks.'):
        _ensure_task_exists(task_id, task_name)
        logger.info(f"Task received by worker: {task_name} [{task_id}]")
        sync_pipeline_task_state(task_id, "RECEIVED")

def on_task_started(event):
    task_id = event.get('uuid')
    logger.info(f"Task started: [{task_id}]")
    sync_pipeline_task_state(task_id, "STARTED")

def on_task_succeeded(event):
    task_id = event.get('uuid')
    result = event.get('result')
    logger.info(f"Task succeeded: [{task_id}]")
    sync_pipeline_task_state(task_id, "SUCCESS", result=result)

def on_task_failed(event):
    task_id = event.get('uuid')
    exception = event.get('exception')
    logger.error(f"Task failed: [{task_id}] - {exception}")
    sync_pipeline_task_state(task_id, "FAILURE", result={"error": str(exception)})

def on_task_revoked(event):
    task_id = event.get('uuid')
    logger.warning(f"Task revoked/terminated: [{task_id}]")
    sync_pipeline_task_state(task_id, "REVOKED", result={"error": "Task was forcefully revoked or terminated."})

def run_monitor():
    logger.info("Starting Celery Event Monitor...")
    with celery_app.connection() as connection:
        recv = celery_app.events.Receiver(connection, handlers={
            'task-sent': on_task_sent,
            'task-received': on_task_received,
            'task-started': on_task_started,
            'task-succeeded': on_task_succeeded,
            'task-failed': on_task_failed,
            'task-revoked': on_task_revoked,
            '*': None,
        })
        try:
            recv.capture(limit=None, timeout=None, wakeup=True)
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user.")
        except Exception as e:
            logger.error(f"Monitor crashed: {e}")
            sys.exit(1)

if __name__ == '__main__':
    run_monitor()
