import scrapy
import psycopg2
import logging
from datetime import datetime
import dateparser
import re

class EgyptArabfinanceSpider(scrapy.Spider):
    name = 'egypt_arabfinance'
    allowed_domains = ['arabfinance.com']
    target_table = 'egy_arabfinance'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.BatchDelayMiddleware': 543,
        },
        'BATCH_SIZE': 500,
        'BATCH_DELAY': 20,
        'ITEM_PIPELINES': {
            'news_scraper.pipelines.PostgresPipeline': 300,
        }
    }

    def __init__(self, *args, **kwargs):
        super(EgyptArabfinanceSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime(2026, 1, 1)
        self.seen_urls = set()

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(EgyptArabfinanceSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider._init_db()
        return spider

    def _init_db(self):
        settings = self.settings.get('POSTGRES_SETTINGS', {})
        if not settings:
            return

        try:
            self.conn = psycopg2.connect(
                dbname=settings['dbname'], user=settings['user'],
                password=settings['password'], host=settings['host'], port=settings['port']
            )
            self.cur = self.conn.cursor()

            self.cur.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.target_table} (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    publish_time TIMESTAMP,
                    author TEXT,
                    content TEXT,
                    site_name TEXT,
                    language TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            self.conn.commit()

            self.cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            max_date = self.cur.fetchone()[0]
            if max_date:
                self.cutoff_date = max_date
                self.logger.info(f"Incremental scraping starting from cutoff date: {self.cutoff_date}")
            else:
                self.logger.info(f"No existing records found. Starting from default cutoff: {self.cutoff_date}")

            self.cur.execute(f"SELECT url FROM {self.target_table}")
            for row in self.cur.fetchall():
                self.seen_urls.add(row[0])

        except Exception as e:
            self.logger.error(f"Failed to connect to DB for initialization: {e}")

    def closed(self, reason):
        if hasattr(self, 'cur'):
            self.cur.close()
        if hasattr(self, 'conn'):
            self.conn.close()

    def start_requests(self):
        # We start with page 1
        url = "https://www.arabfinance.com/en/news/newssinglecategory/2"
        yield scrapy.Request(url, callback=self.parse_list, cb_kwargs={'page': 1})

    def parse_list(self, response, page):
        articles = response.css('a[href*="/en/news/newdetails/"]')
        found_new = False
        
        for a in articles:
            link = a.attrib.get('href')
            if not link:
                continue
                
            full_url = response.urljoin(link)
            if full_url in self.seen_urls:
                continue

            found_new = True
            self.seen_urls.add(full_url)

            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
            )

        # Pagination logic
        pagination_spans = response.css('.pagination-results .pagination-number::text').getall()
        max_page = 100 # default fallback
        if pagination_spans and len(pagination_spans) >= 2:
            try:
                max_page = int(pagination_spans[-1].strip())
            except ValueError:
                pass
                
        if found_new and page < max_page:
            next_page = page + 1
            next_url = f"https://www.arabfinance.com/en/news/newssinglecategory/2?page={next_page}"
            yield scrapy.Request(next_url, callback=self.parse_list, cb_kwargs={'page': next_page})

    def parse_article(self, response):
        title = response.css('h1::text, h2.title::text').get()
        if title:
            title = title.strip()
        else:
            title = "Unknown Title"

        # Date parsing
        # It typically looks like: "Updated 3/18/2026 1:39:00 PM"
        publish_time = datetime.now()
        date_text = None
        
        for el in response.xpath('//*[contains(text(), "Updated ")]'):
            text = el.xpath('normalize-space(.)').get()
            if text and "Updated" in text and "202" in text:
                date_text = text
                break
                
        if not date_text:
            date_el = response.css('time, .date, .posted-on').getall()
            for d in date_el:
                if '202' in d:
                    date_text = d
                    break

        if date_text:
            # clean up "Updated " prefix if exists
            clean_date_str = date_text.replace("Updated", "").strip()
            parsed_date = dateparser.parse(clean_date_str, settings={'TIMEZONE': 'UTC'})
            if parsed_date:
                publish_time = parsed_date.replace(tzinfo=None)

        # Content parsing
        content_parts = []
        for p in response.css('p'):
            # Some sites have script tags or unwanted classes inside p, we clean text
            text = ' '.join(p.xpath('.//text()').extract()).strip()
            
            # Avoid picking up empty paragraphs or UI artifacts like "Back to category"
            if text and len(text) > 10 and not "\n" in text[:5]:
                content_parts.append(text)

        content = '\n\n'.join(content_parts)
        
        if not content:
            return

        if publish_time < self.cutoff_date:
            return

        yield {
            'url': response.url,
            'title': title,
            'publish_time': publish_time,
            'author': 'ArabFinance',
            'content': content.strip(),
            'site_name': 'arabfinance',
            'language': 'en'
        }
