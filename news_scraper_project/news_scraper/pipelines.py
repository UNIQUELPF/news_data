import psycopg2
from datetime import datetime

class PostgresPipeline:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self._ensured_tables = set()

    def open_spider(self, spider):
        settings = spider.settings.get('POSTGRES_SETTINGS')
        self.connection = psycopg2.connect(
            dbname=settings['dbname'],
            user=settings['user'],
            password=settings['password'],
            host=settings['host'],
            port=settings['port']
        )
        self.cursor = self.connection.cursor()

    def close_spider(self, spider):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def process_item(self, item, spider):
        # Table routing based on spider attribute or name
        table_name = getattr(spider, 'target_table', None)
        if not table_name:
            # Fallback logic if target_table is not defined
            if spider.name == 'danas': table_name = 'ser_danas'
            elif spider.name == 'b92': table_name = 'ser_b92'
            elif spider.name == 'politika': table_name = 'ser_politika'
            elif spider.name == 'economy': table_name = 'aze_economy'
            elif spider.name == 'bfb': table_name = 'aze_bfb'
            else:
                spider.logger.error(f"No target table defined for spider {spider.name}")
                return item

        try:
            self._ensure_table(table_name)
            url = self._sanitize_value(item.get('url'))
            title = self._sanitize_value(item.get('title'))
            content = self._sanitize_value(item.get('content'))
            author = self._sanitize_value(item.get('author'))
            language = self._sanitize_value(item.get('language'))
            section = self._sanitize_value(item.get('section'))

            # Check if item has a 'section' field (e.g. Economic Times spider)
            if section:
                self.cursor.execute(
                    f"""
                    INSERT INTO {table_name} (url, title, content, publish_time, author, language, section)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO UPDATE SET
                        title = EXCLUDED.title,
                        content = EXCLUDED.content,
                        publish_time = COALESCE(EXCLUDED.publish_time, {table_name}.publish_time),
                        author = EXCLUDED.author,
                        language = EXCLUDED.language,
                        section = EXCLUDED.section
                    """,
                    (
                        url,
                        title,
                        content,
                        item['publish_time'],
                        author,
                        language,
                        section
                    )
                )
            else:
                self.cursor.execute(
                    f"""
                    INSERT INTO {table_name} (url, title, content, publish_time, author, language)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO UPDATE SET
                        title = EXCLUDED.title,
                        content = EXCLUDED.content,
                        publish_time = COALESCE(EXCLUDED.publish_time, {table_name}.publish_time),
                        author = EXCLUDED.author,
                        language = EXCLUDED.language
                    """,
                    (
                        url,
                        title,
                        content,
                        item['publish_time'],
                        author,
                        language
                    )
                )
            self.connection.commit()
            if self.cursor.rowcount == 1:
                spider.logger.info(f"Saved to DB: {url}")
        except Exception as e:
            spider.logger.error(f"Error saving to DB: {e}")
            self.connection.rollback()
        return item

    def _ensure_table(self, table_name):
        if table_name in self._ensured_tables:
            return

        self.cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                content TEXT,
                publish_time TIMESTAMP,
                author TEXT,
                language TEXT,
                section TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.commit()
        self._ensured_tables.add(table_name)

    def _sanitize_value(self, value):
        if value is None:
            return None
        return str(value).replace("\x00", " ").strip()
