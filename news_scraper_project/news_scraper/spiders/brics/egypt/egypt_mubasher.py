import scrapy
import psycopg2
import logging
from datetime import datetime
import re
import json
from scrapy.exceptions import CloseSpider

class EgyptMubasherSpider(scrapy.Spider):
    name = 'egypt_mubasher'
    allowed_domains = ['english.mubasher.info']
    target_table = 'egy_mubasher'

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
        super(EgyptMubasherSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime(2026, 1, 1)
        self.seen_urls = set()

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(EgyptMubasherSpider, cls).from_crawler(crawler, *args, **kwargs)
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
        url = "https://english.mubasher.info/news/sa/now/latest"
        yield scrapy.Request(url, callback=self.parse_list, cb_kwargs={'page': 1})

    def parse_list(self, response, page):
        # Extract article links from raw HTML using regex (AngularJS page, links are in href attributes)
        raw_html = response.text
        article_links = re.findall(r'href=["\']?(/news/\d+/[^"\'>\s]+)', raw_html)

        # Deduplicate within page
        unique_links = list(dict.fromkeys(article_links))

        if not unique_links:
            self.logger.info(f"No articles found on page {page}. Stopping.")
            return

        found_new = False
        for link in unique_links:
            full_url = "https://english.mubasher.info" + link
            if full_url in self.seen_urls:
                continue

            found_new = True
            self.seen_urls.add(full_url)

            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
            )

        # Extract pagination info
        num_pages_match = re.search(r'window\.midata\.numPages\s*=\s*(\d+)', raw_html)
        max_pages = int(num_pages_match.group(1)) if num_pages_match else 100

        if found_new and page < max_pages:
            next_page = page + 1
            next_url = f"https://english.mubasher.info/news/sa/now/latest//{next_page}"
            yield scrapy.Request(next_url, callback=self.parse_list, cb_kwargs={'page': next_page})

    def parse_article(self, response):
        raw_html = response.text

        # Try to extract window.article JS object
        match = re.search(r"window\.article\s*=\s*(\{[\s\S]*?\})\s*;", raw_html)

        title = None
        publish_time = None
        content = None
        author = "Mubasher"

        if match:
            raw_js = match.group(1)
            # Extract fields using regex from JS object (not valid JSON, uses single quotes)
            title_match = re.search(r"'title'\s*:\s*'((?:[^'\\]|\\.)*)'", raw_js)
            if not title_match:
                title_match = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_js)
            if title_match:
                title = title_match.group(1).replace("\\'", "'").replace('\\"', '"')

            # Extract publishedAt
            date_match = re.search(r"'publishedAt'\s*:\s*'([^']+)'", raw_js)
            if not date_match:
                date_match = re.search(r'"publishedAt"\s*:\s*"([^"]+)"', raw_js)
            if date_match:
                date_str = date_match.group(1)
                try:
                    publish_time = datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=None)
                except Exception:
                    publish_time = datetime.now()

            # Extract body (HTML content)
            body_match = re.search(r"'body'\s*:\s*'((?:[^'\\]|\\.)*)'", raw_js)
            if not body_match:
                body_match = re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_js)
            if body_match:
                body_html = body_match.group(1).replace("\\'", "'").replace('\\"', '"').replace('\\/', '/')
                from bs4 import BeautifulSoup
                body_soup = BeautifulSoup(body_html, 'html.parser')
                content = body_soup.get_text(separator='\n', strip=True)

        # Fallback: parse from DOM if window.article extraction failed
        if not title:
            title_el = response.css('h1::text, .article-title::text, .md-news-details__title::text').get()
            title = title_el.strip() if title_el else "Unknown Title"

        if not publish_time:
            publish_time = datetime.now()

        if not content:
            paragraphs = response.css('.article-body p, .md-news-details__content p, article p, .the-news p')
            body_parts = []
            for p in paragraphs:
                texts = p.xpath('.//text()').getall()
                text = ' '.join(t.strip() for t in texts if t.strip())
                if text:
                    body_parts.append(text)
            content = '\n\n'.join(body_parts)

        if not content or not content.strip():
            return

        if publish_time < self.cutoff_date:
            return

        yield {
            'url': response.url,
            'title': title,
            'publish_time': publish_time,
            'author': author,
            'content': content.strip(),
            'site_name': 'mubasher',
            'language': 'en'
        }
