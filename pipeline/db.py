import os

import psycopg2


def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "scrapy_db"),
        user=os.getenv("POSTGRES_USER", "your_user"),
        password=os.getenv("POSTGRES_PASSWORD", "your_password"),
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
    )
