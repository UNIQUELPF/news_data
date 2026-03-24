import psycopg2
from datetime import datetime

class PostgresPipeline:
    def __init__(self):
        self.connection = None
        self.cursor = None

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
            # Check if item has a 'section' field (e.g. Economic Times spider)
            if 'section' in item and item.get('section'):
                self.cursor.execute(
                    f"INSERT INTO {table_name} (url, title, content, publish_time, author, language, section) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (url) DO NOTHING",
                    (
                        item['url'],
                        item['title'],
                        item['content'],
                        item['publish_time'],
                        item['author'],
                        item['language'],
                        item['section']
                    )
                )
            else:
                self.cursor.execute(
                    f"INSERT INTO {table_name} (url, title, content, publish_time, author, language) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (url) DO NOTHING",
                    (
                        item['url'],
                        item['title'],
                        item['content'],
                        item['publish_time'],
                        item['author'],
                        item['language']
                    )
                )
            self.connection.commit()
            if self.cursor.rowcount == 1:
                spider.logger.info(f"Saved to DB: {item['url']}")
        except Exception as e:
            spider.logger.error(f"Error saving to DB: {e}")
            self.connection.rollback()
        return item
