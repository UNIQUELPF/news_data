import logging
from datetime import datetime

import psycopg2
from psycopg2 import sql


def _fallback_settings():
    from .settings import ENABLE_UNIFIED_PIPELINE, POSTGRES_SETTINGS

    return {
        "POSTGRES_SETTINGS": POSTGRES_SETTINGS,
        "ENABLE_UNIFIED_PIPELINE": ENABLE_UNIFIED_PIPELINE,
    }


def _normalize_settings(settings):
    return settings or _fallback_settings()

def _get_db_connection(settings):
    settings = _normalize_settings(settings)
    conn_params = settings.get('POSTGRES_SETTINGS')
    return psycopg2.connect(
        dbname=conn_params['dbname'],
        user=conn_params['user'],
        password=conn_params['password'],
        host=conn_params['host'],
        port=conn_params['port']
    )

def _use_unified_pipeline(settings):
    settings = _normalize_settings(settings)
    value = settings.get('ENABLE_UNIFIED_PIPELINE', True)
    if isinstance(value, str):
        return value.lower() in ('1', 'true', 'yes', 'on')
    return bool(value)

def get_incremental_state(
    settings,
    spider_name=None,
    table_name=None,
    default_cutoff=None,
    full_scan=False,
    url_limit=5000,
):
    """
    Return incremental state with unified `articles` table preferred and legacy table fallback.

    Result:
    - cutoff_date: latest publish_time when available, otherwise default_cutoff
    - scraped_urls: recent urls for duplicate filtering
    - source: unified / legacy / default
    """
    logger = logging.getLogger(__name__)
    settings = _normalize_settings(settings)
    default_cutoff = default_cutoff or datetime(2025, 12, 31)
    state = {
        "cutoff_date": default_cutoff,
        "scraped_urls": set(),
        "source": "default",
    }

    try:
        conn = _get_db_connection(settings)
        cursor = conn.cursor()

        if _use_unified_pipeline(settings) and spider_name:
            cursor.execute(
                """
                SELECT a.publish_time, a.source_url
                FROM articles a
                JOIN sources s ON s.id = a.source_id
                WHERE s.spider_name = %s
                ORDER BY a.publish_time DESC NULLS LAST, a.id DESC
                LIMIT %s
                """,
                (spider_name, url_limit),
            )
            rows = cursor.fetchall()
            if rows:
                latest_publish_time = rows[0][0]
                if latest_publish_time and not full_scan:
                    state["cutoff_date"] = latest_publish_time.replace(tzinfo=None) if latest_publish_time.tzinfo else latest_publish_time
                state["scraped_urls"] = {row[1] for row in rows if row[1]}
                state["source"] = "unified"
                cursor.close()
                conn.close()
                return state

        if table_name:
            cursor.execute(
                sql.SQL("SELECT MAX(publish_time) FROM {}").format(sql.Identifier(table_name))
            )
            max_time = cursor.fetchone()[0]
            cursor.execute(
                sql.SQL("SELECT url FROM {} ORDER BY publish_time DESC NULLS LAST LIMIT %s").format(
                    sql.Identifier(table_name)
                ),
                (url_limit,),
            )
            rows = cursor.fetchall()
            if max_time and not full_scan:
                state["cutoff_date"] = max_time.replace(tzinfo=None) if getattr(max_time, "tzinfo", None) else max_time
            state["scraped_urls"] = {row[0] for row in rows if row[0]}
            state["source"] = "legacy"

        cursor.close()
        conn.close()
    except psycopg2.errors.UndefinedTable:
        logger.info(f"Legacy table '{table_name}' not found, using default cutoff.")
    except psycopg2.errors.UndefinedColumn:
        logger.info("Unified tables not ready yet, falling back to default cutoff.")
    except Exception as exc:
        logger.warning(
            f"get_incremental_state failed for spider='{spider_name}', table='{table_name}': {exc}"
        )

    return state

def get_dynamic_cutoff(settings, table_name, is_string_format=False, spider_name=None, default_cutoff=None):
    """
    Dynamic cutoff helper for incremental scraping.

    - Prefer unified `articles` data when available.
    - Fall back to legacy spider table when unified data is absent.
    - If data exists: returns today's 00:00 cutoff.
    - If data is empty/not found/error: returns first-run cutoff (2025-12-31).
    - If is_string_format=True: returns YYYYMMDD string.
    """
    first_time_date = default_cutoff or datetime(2025, 12, 31)
    subsequent_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    state = get_incremental_state(
        settings,
        spider_name=spider_name,
        table_name=table_name,
        default_cutoff=first_time_date,
        full_scan=False,
        url_limit=1,
    )
    cutoff = subsequent_date if state["source"] in ("unified", "legacy") else first_time_date

    if is_string_format:
        return cutoff.strftime("%Y%m%d")
    return cutoff
