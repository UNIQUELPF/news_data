import psycopg2
from datetime import datetime
import logging

def get_dynamic_cutoff(settings, table_name, is_string_format=False):
    """
    Dynamic cutoff helper for incremental scraping.

    - If table has data: returns today's 00:00 cutoff.
    - If table is empty/not found/error: returns first-run cutoff (2025-12-31).
    - If is_string_format=True: returns YYYYMMDD string.
    """
    logger = logging.getLogger(__name__)
    first_time_date = datetime(2025, 12, 31)
    subsequent_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = first_time_date

    try:
        conn_params = settings.get('POSTGRES_SETTINGS')
        conn = psycopg2.connect(
            dbname=conn_params['dbname'],
            user=conn_params['user'],
            password=conn_params['password'],
            host=conn_params['host'],
            port=conn_params['port']
        )
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        if count and count > 0:
            cutoff = subsequent_date
    except psycopg2.errors.UndefinedTable:
        logger.info(f"Table '{table_name}' not found, using first-run cutoff.")
    except Exception as exc:
        logger.warning(f"get_dynamic_cutoff failed for '{table_name}': {exc}")

    if is_string_format:
        return cutoff.strftime("%Y%m%d")
    return cutoff
