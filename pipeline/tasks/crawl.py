import os
import subprocess
from datetime import datetime

from scrapy.utils.project import get_project_settings
from scrapy.spiderloader import SpiderLoader
from celery import group, chain

from pipeline.celery_app import celery_app
from pipeline.db import get_db_connection

DEFAULT_PROJECT_DIR = os.getenv("SCRAPY_PROJECT_DIR", "/app/news_scraper_project")
CRAWL_BATCH_SIZE = int(os.getenv("CRAWL_BATCH_SIZE", "5"))

def get_all_spiders() -> list[str]:
    """Dynamically discover all available spiders in the Scrapy project."""
    settings = get_project_settings()
    # Explicitly set the project directory if we're not in it
    if "SETTING_PRIORITY" not in settings:
         os.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'news_scraper.settings')
         settings = get_project_settings()
    
    loader = SpiderLoader.from_settings(settings)
    return sorted(loader.list())


def _build_scrapy_env(project_dir: str) -> dict:
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = project_dir if not pythonpath else os.pathsep.join([project_dir, pythonpath])
    return env


def _create_crawl_job(spider_name: str) -> int | None:
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO crawl_jobs (spider_name, status, started_at, items_scraped)
            VALUES (%s, 'running', CURRENT_TIMESTAMP, 0)
            RETURNING id
            """,
            (spider_name,),
        )
        job_id = cursor.fetchone()[0]
        connection.commit()
        return job_id
    except Exception:
        if connection:
            connection.rollback()
        return None
    finally:
        if connection:
            connection.close()


def _finish_crawl_job(job_id: int | None, *, status: str, items_scraped: int = 0, error_message: str | None = None) -> None:
    if not job_id:
        return

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE crawl_jobs
            SET finished_at = CURRENT_TIMESTAMP,
                status = %s,
                items_scraped = %s,
                error_message = %s
            WHERE id = %s
            """,
            (status, items_scraped, error_message, job_id),
        )
        connection.commit()
    except Exception:
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()


def _extract_items_scraped(stdout: str | None) -> int:
    if not stdout:
        return 0

    marker = "'item_scraped_count':"
    index = stdout.rfind(marker)
    if index == -1:
        return 0

    tail = stdout[index + len(marker):].strip()
    digits = []
    for char in tail:
        if char.isdigit():
            digits.append(char)
        elif digits:
            break
    return int("".join(digits)) if digits else 0


@celery_app.task(name="pipeline.tasks.crawl.run_spider")
def run_spider(spider_name: str, extra_args: dict | None = None, parent_task_id: str | None = None) -> dict:
    project_dir = DEFAULT_PROJECT_DIR
    env = _build_scrapy_env(project_dir)
    cmd = ["scrapy", "crawl", spider_name]
    job_id = _create_crawl_job(spider_name)

    for key, value in (extra_args or {}).items():
        cmd.extend(["-a", f"{key}={value}"])

    started_at = datetime.now().isoformat()
    try:
        completed = subprocess.run(
            cmd,
            cwd=project_dir,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        items_scraped = _extract_items_scraped(completed.stdout)
        _finish_crawl_job(job_id, status="success", items_scraped=items_scraped)
        return {
            "spider": spider_name,
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(),
            "status": "success",
            "items_scraped": items_scraped,
            "stdout_tail": completed.stdout[-4000:],
        }
    except subprocess.CalledProcessError as exc:
        items_scraped = _extract_items_scraped(exc.stdout)
        _finish_crawl_job(
            job_id,
            status="failed",
            items_scraped=items_scraped,
            error_message=(exc.stderr or exc.stdout or "")[-2000:],
        )
        return {
            "spider": spider_name,
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(),
            "status": "failed",
            "items_scraped": items_scraped,
            "returncode": exc.returncode,
            "stdout_tail": (exc.stdout or "")[-4000:],
            "stderr_tail": (exc.stderr or "")[-4000:],
        }


@celery_app.task(name="pipeline.tasks.crawl.run_all_spiders_automatic", bind=True)
def run_all_spiders_automatic(self) -> dict:
    """
    Orchestrate all discovered spiders in batches.
    Uses Celery's chain and group to throttle execution.
    """
    all_spiders = get_all_spiders()
    parent_id = self.request.id
    
    if not all_spiders:
        return {"status": "empty", "message": "No spiders found in project"}

    # Split into batches of size CRAWL_BATCH_SIZE
    batches = [all_spiders[i:i + CRAWL_BATCH_SIZE] for i in range(0, len(all_spiders), CRAWL_BATCH_SIZE)]
    
    # Build a chain of groups
    task_chain = []
    for batch in batches:
        # Each group contains spiders that will run in parallel
        # We pass parent_task_id so they can be aggregated in the UI
        s_group = group(run_spider.s(spider_name=name, parent_task_id=parent_id) for name in batch)
        task_chain.append(s_group)
    
    # Execute the chain
    chain(*task_chain).delay()
    
    return {
        "status": "triggered",
        "total_spiders": len(all_spiders),
        "batch_count": len(batches),
        "batch_size": CRAWL_BATCH_SIZE,
        "parent_task_id": parent_id
    }


@celery_app.task(name="pipeline.tasks.crawl.manual_ingest_from_spiders", bind=True)
def manual_ingest_from_spiders(self, spiders: list[str]) -> dict:
    """Manually triggered ingestion for a specific list of spiders."""
    if not spiders:
        return {"status": "empty", "message": "No spiders selected"}
    
    parent_id = self.request.id
    # Split into batches
    batches = [spiders[i:i + CRAWL_BATCH_SIZE] for i in range(0, len(spiders), CRAWL_BATCH_SIZE)]
    
    task_chain = []
    for batch in batches:
        s_group = group(run_spider.s(spider_name=name, parent_task_id=parent_id) for name in batch)
        task_chain.append(s_group)
    
    chain(*task_chain).delay()
    
    return {
        "status": "triggered",
        "count": len(spiders),
        "parent_task_id": parent_id
    }
