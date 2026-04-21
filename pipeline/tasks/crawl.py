import os
import subprocess
from datetime import datetime

from scrapy.utils.project import get_project_settings
from scrapy.spiderloader import SpiderLoader
from celery import group, chain

from pipeline.celery_app import celery_app
from pipeline.db import get_db_connection
from pipeline.task_state import record_pipeline_task, sync_pipeline_task_state, classify_task_type

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


import billiard
import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scrapy.signalmanager import dispatcher

def _execute_spider(spider_name: str, extra_args: dict, result_queue: billiard.Queue):
    """
    Internal function to run Scrapy in a dedicated process.
    """
    try:
        # Load settings and set the module environment
        os.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'news_scraper.settings')
        settings = get_project_settings()
        
        # This container will hold our results
        stats_result = {"items": 0, "status": "failed", "error": None}
        
        def collect_stats(spider):
            # This is called when spider is closed
            stats = crawler.stats
            stats_result["items"] = stats.get_value('item_scraped_count', 0)
            stats_result["status"] = "success"

        # Initialize Crawler and connect signal
        process = CrawlerProcess(settings)
        crawler = process.create_crawler(spider_name)
        
        # Connect the spider_closed signal to our collector
        dispatcher.connect(collect_stats, signal=scrapy.signals.spider_closed)
        
        process.crawl(crawler, **(extra_args or {}))
        process.start() # Blocks until finished
        
        result_queue.put(stats_result)
    except Exception as e:
        import traceback
        result_queue.put({"items": 0, "status": "failed", "error": f"{str(e)}\n{traceback.format_exc()}"})

@celery_app.task(name="pipeline.tasks.crawl.run_spider", bind=True)
def run_spider(self, spider_name: str, extra_args: dict | None = None, parent_task_id: str | None = None) -> dict:
    task_id = self.request.id
    started_at = datetime.now().isoformat()
    
    # 1. Register task in tracking table
    record_pipeline_task(
        task_id=task_id,
        task_name=f"Crawl: {spider_name}",
        task_type="crawl",
        params={"spider_name": spider_name, "extra_args": extra_args},
        parent_task_id=parent_task_id,
        state="RUNNING"
    )
    
    job_id = _create_crawl_job(spider_name)
    
    result_queue = billiard.Queue()
    p = billiard.Process(
        target=_execute_spider, 
        args=(spider_name, extra_args or {}, result_queue)
    )
    
    try:
        p.start()
        p.join() # Wait for spider to finish
        
        result = {"items": 0, "status": "failed", "error": "Process terminated unexpectedly"}
        if not result_queue.empty():
            result = result_queue.get()
            
        status = result["status"]
        items_scraped = result["items"]
        error_message = result["error"]
        
        # 2. Update status in our tracking tables
        _finish_crawl_job(job_id, status=status, items_scraped=items_scraped, error_message=error_message)
        
        celery_state = "SUCCESS" if status == "success" else "FAILURE"
        sync_pipeline_task_state(
            task_id=task_id, 
            state=celery_state, 
            result={"items_scraped": items_scraped, "error": error_message}
        )
        
        return {
            "spider": spider_name,
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(),
            "status": status,
            "items_scraped": items_scraped,
            "error": error_message
        }
    except Exception as e:
        import traceback
        err_msg = f"{str(e)}\n{traceback.format_exc()}"
        _finish_crawl_job(job_id, status="failed", items_scraped=0, error_message=err_msg)
        sync_pipeline_task_state(task_id=task_id, state="FAILURE", result={"error": err_msg})
        return {
            "spider": spider_name,
            "status": "failed",
            "error": err_msg
        }


@celery_app.task(name="pipeline.tasks.crawl.run_all_spiders_automatic", bind=True)
def run_all_spiders_automatic(self) -> dict:
    """
    Orchestrate all discovered spiders in a streaming fashion.
    Tasks are dispatched individually to the Celery queue.
    """
    all_spiders = get_all_spiders()
    parent_id = self.request.id
    
    # Register parent task
    record_pipeline_task(
        task_id=parent_id,
        task_name="Crawler Auto-Cruise (Streaming)",
        task_type="crawl",
        params={"spider_count": len(all_spiders)},
        state="RUNNING"
    )
    
    if not all_spiders:
        return {"status": "empty", "message": "No spiders found in project"}

    # Dispatch all tasks to the queue. Celery handles the concurrency.
    for name in all_spiders:
        run_spider.delay(spider_name=name, parent_task_id=parent_id)
    
    result = {
        "status": "dispatched",
        "total_spiders": len(all_spiders),
        "parent_task_id": parent_id
    }
    sync_pipeline_task_state(task_id=parent_id, state="SUCCESS", result=result)
    
    return result


@celery_app.task(name="pipeline.tasks.crawl.manual_ingest_from_spiders", bind=True)
def manual_ingest_from_spiders(self, spiders: list[str]) -> dict:
    """Manually triggered ingestion for a specific list of spiders."""
    if not spiders:
        return {"status": "empty", "message": "No spiders selected"}
    
    parent_id = self.request.id
    
    # Register parent task
    record_pipeline_task(
        task_id=parent_id,
        task_name="Manual Ingestion (Streaming)",
        task_type="crawl",
        params={"spiders": spiders},
        state="RUNNING"
    )
    
    # Dispatch all tasks
    for name in spiders:
        run_spider.delay(spider_name=name, parent_task_id=parent_id)
    
    result = {
        "status": "dispatched",
        "count": len(spiders),
        "parent_task_id": parent_id
    }
    sync_pipeline_task_state(task_id=parent_id, state="SUCCESS", result=result)
    
    return result
