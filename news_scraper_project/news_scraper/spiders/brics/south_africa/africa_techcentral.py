# 南非africa techcentral爬虫，负责抓取对应站点、机构或栏目内容。

import re
from datetime import datetime

import psycopg2
import scrapy
from news_scraper.utils import get_incremental_state


class AfricaTechCentralSpider(scrapy.Spider):
    name = 'africa_techcentral'

    country_code = 'ZAF'

    country = '南非'
    allowed_domains = ['techcentral.co.za']
    target_table = 'afr_techcentral'

    # Do not use anti-fingerprint tools unless necessary
    use_curl_cffi = False

    custom_settings = {
        'CLOSESPIDER_ITEMCOUNT': 2000,
        # No direct delay
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
        super(AfricaTechCentralSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime(2026, 1, 1)
        self.seen_urls = set()
        
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(AfricaTechCentralSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider._init_db()
        return spider
        
    def _init_db(self):
        settings = self.settings.get('POSTGRES_SETTINGS', {})
        if not settings:
            return
            
        try:
            conn = psycopg2.connect(
                dbname=settings['dbname'], user=settings['user'],
                password=settings['password'], host=settings['host'], port=settings['port']
            )
            cur = conn.cursor()
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.target_table} (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    publish_time TIMESTAMP,
                    author TEXT,
                    content TEXT,
                    url TEXT UNIQUE,
                    language TEXT,
                    section TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
            cur.close()
            conn.close()

            state = get_incremental_state(
                self.settings,
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=self.cutoff_date,
                full_scan=False,
            )
            self.cutoff_date = state["cutoff_date"]
            self.seen_urls = state["scraped_urls"]
        except Exception as e:
            self.logger.error(f"Failed to connect to DB for initialization: {e}")

    def closed(self, reason):
        return

    def start_requests(self):
        # Initial request to page 1
        url = "https://techcentral.co.za/category/news/page/1/"
        yield scrapy.Request(url, callback=self.parse_list, cb_kwargs={'page': 1})

    def parse_list(self, response, page):
        articles = response.css('article')
        if not articles:
            self.logger.info(f"No articles found on page {page}. Stopping.")
            return

        all_old = True
        for article in articles:
            # title & link
            title_node = article.css('h2.is-title a, h3.title a, a.image-link')
            link = title_node.css('::attr(href)').get()
            title = title_node.css('::text').get() or title_node.css('::attr(title)').get() or "Unknown Title"
            
            if not link:
                continue

            title = title.strip()
            
            # datetime
            time_node = article.css('time::attr(datetime)')
            date_str = time_node.get()
            
            publish_time = None
            if date_str:
                try:
                    publish_time = datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=None)
                except Exception:
                    pass
            
            if not publish_time:
                publish_time = datetime.now()

            # check cutoff
            if publish_time >= self.cutoff_date:
                all_old = False
            else:
                continue

            if link not in self.seen_urls:
                self.seen_urls.add(link)
                
                yield scrapy.Request(
                    link,
                    callback=self.parse_article,
                    cb_kwargs={'title': title, 'publish_time': publish_time}
                )

        if not all_old and len(articles) > 0:
            next_page = page + 1
            next_url = f"https://techcentral.co.za/category/news/page/{next_page}/"
            yield scrapy.Request(next_url, callback=self.parse_list, cb_kwargs={'page': next_page})

    def parse_article(self, response, title, publish_time):
        # find author
        author = response.css('span.meta-author a::text, a.author::text, meta[name="author"]::attr(content)').get()
        if author:
            author = author.strip()
        
        # paragraphs
        paragraphs = response.css('div.post-content p, div.entry-content p')
        if not paragraphs:
            paragraphs = response.css('p')
            
        content_text = ' '.join([p.css('::text').getall() and ' '.join(p.css('::text').getall()).strip() or '' for p in paragraphs])
        content_text = re.sub(r'\s+', ' ', content_text).strip()

        if not content_text:
            return

        yield {
            'url': response.url,
            'title': title,
            'publish_time': publish_time,
            'author': author,
            'content': content_text,
            'language': 'en'
        }
