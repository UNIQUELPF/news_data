import scrapy
import psycopg2
import logging
import json
from datetime import datetime
import re

class AfricaIolSpider(scrapy.Spider):
    name = 'africa_iol'
    allowed_domains = ['iol.co.za']
    target_table = 'afr_iol'

    use_curl_cffi = True

    custom_settings = {
        'CLOSESPIDER_ITEMCOUNT': 0,
        'DOWNLOAD_DELAY': 0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 500,
            'news_scraper.middlewares.BatchDelayMiddleware': 543,
        },
        'BATCH_SIZE': 500,
        'BATCH_DELAY': 20,
        'ITEM_PIPELINES': {
            'news_scraper.pipelines.PostgresPipeline': 300,
        }
    }

    def __init__(self, *args, **kwargs):
        super(AfricaIolSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime(2026, 1, 1)
        self.seen_urls = set()
        
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(AfricaIolSpider, cls).from_crawler(crawler, *args, **kwargs)
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
        yield self.make_api_request(page=1)

    def make_api_request(self, page):
        url = f"https://iol.co.za/api-proxy/apiv1/pub/articles/get-all/?exclude_fields=widgets,images,blur&limit=100&publication=iol&section=business&subsection=economy&page={page}"
        headers = {
            "consumer-key": "759d7cf855545a3177a2ca5ecbebbc83b74b5cb8",
            "referer": "https://iol.co.za/business/economy/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"
        }
        return scrapy.Request(
            url,
            headers=headers,
            callback=self.parse_api_response,
            cb_kwargs={'page': page},
            dont_filter=True
        )

    def parse_api_response(self, response, page):
        try:
            data = json.loads(response.body)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON on page {page}: {e}")
            return

        if not data:
            self.logger.info(f"Empty data on page {page}. Stopping pagination.")
            return

        found_new = False
        all_old = True

        for item in data:
            pub_url = item.get('pub_url')
            if not pub_url:
                continue
                
            full_url = "https://www.iol.co.za" + pub_url if not pub_url.startswith('http') else pub_url
            
            # published looks like epoch ms or string? Subagent said "Epoch ms" but let's be careful
            pub_val = item.get('published')
            publish_time = None
            if isinstance(pub_val, dict) and '$date' in pub_val:
                try:
                    publish_time = datetime.fromtimestamp(int(pub_val['$date']) / 1000.0)
                except Exception:
                    pass
            elif isinstance(pub_val, (int, float)):
                # epoch ms or s
                try:
                    if pub_val > 253402300799: # Larger than year 9999 in seconds, likely ms
                        publish_time = datetime.fromtimestamp(pub_val / 1000.0)
                    else:
                        publish_time = datetime.fromtimestamp(pub_val)
                except Exception:
                    pass
            elif isinstance(pub_val, str):
                try:
                    # try to parse as iso format
                    publish_time = datetime.fromisoformat(pub_val.replace('Z', '+00:00')).replace(tzinfo=None)
                except Exception:
                    pass

            if not publish_time:
                publish_time = datetime.now()

            if publish_time.tzinfo is not None:
                publish_time = publish_time.replace(tzinfo=None)

            if publish_time >= self.cutoff_date:
                all_old = False
            else:
                continue # skip older articles

            if full_url not in self.seen_urls:
                found_new = True
                self.seen_urls.add(full_url)
                
                title = item.get('title', 'Untitled')
                
                authors = item.get('authors', [])
                author_names = [a.get('name') for a in authors if type(a) == dict and a.get('name')]
                author = ', '.join(author_names) if author_names else None
                
                content_text = item.get('plain_text', '').strip()
                if not content_text:
                    continue
                
                yield {
                    'url': full_url,
                    'title': title,
                    'publish_time': publish_time,
                    'author': author,
                    'content': content_text,
                    'language': 'en'
                }

        if not all_old and len(data) > 0:
            yield self.make_api_request(page + 1)


