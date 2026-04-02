# 印度entrackr爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from datetime import datetime
import psycopg2
import logging
import re
from scrapy.spidermiddlewares.httperror import HttpError
from scrapy.exceptions import CloseSpider
from twisted.internet.error import TimeoutError, TCPTimedOutError

class IndiaEntrackrSpider(scrapy.Spider):
    name = 'india_entrackr'
    allowed_domains = ['entrackr.com']
    target_table = 'ind_entrackr'
    
    use_curl_cffi = True

    custom_settings = {
        'CLOSESPIDER_ITEMCOUNT': 0,
        'DOWNLOAD_DELAY': 2.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 500,
            'news_scraper.middlewares.BatchDelayMiddleware': 543,
        },
        'BATCH_SIZE': 500,
        'BATCH_DELAY': 30,
        'ITEM_PIPELINES': {
            'news_scraper.pipelines.PostgresPipeline': 300,
        }
    }

    def __init__(self, *args, **kwargs):
        super(IndiaEntrackrSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime(2026, 1, 1)
        self.seen_urls = set()
        settings = self.custom_settings
        
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(IndiaEntrackrSpider, cls).from_crawler(crawler, *args, **kwargs)
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
            
            # Get latest date
            self.cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            max_date = self.cur.fetchone()[0]
            if max_date:
                self.cutoff_date = max_date
                self.logger.info(f"Incremental scraping starting from cutoff date: {self.cutoff_date}")
            else:
                self.logger.info(f"No existing records found. Starting from default cutoff: {self.cutoff_date}")
                
            # Preload seen URLs
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
        yield self.make_page_request(1)

    def make_page_request(self, page):
        if page == 1:
            url = 'https://entrackr.com/news'
        else:
            url = f'https://entrackr.com/news?page={page}'
        return scrapy.Request(
            url,
            callback=self.parse_list,
            cb_kwargs={'page': page},
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'},
            errback=self.errback_httpbin
        )

    def parse_list(self, response, page):
        all_links = response.css('a::attr(href)').getall()
        # Find article links containing /news/ and optionally a hyphen with digits
        article_links = [l for l in all_links if '/news/' in l and re.search(r'-\d+$', l.split('?')[0])]
        article_links = list(set(article_links))

        for link in article_links:
            if not link.startswith('http'):
                link = 'https://entrackr.com' + link

            if link not in self.seen_urls:
                self.seen_urls.add(link)
                yield scrapy.Request(
                    link, 
                    callback=self.parse_article,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'},
                    errback=self.errback_httpbin
                )

        # Unconditionally paginate; we will close the spider natively if we hit the cutoff date in parse_article
        next_page = page + 1
        yield self.make_page_request(next_page)

    def parse_article(self, response):
        title = response.css('h1::text').get()
        if not title:
            title = response.css('title::text').get()

        date_str = response.css('time::text').get()
        if not date_str:
            date_str = response.css('.date::text, [class*="date"]::text, [class*="time"]::text').get()
        
        publish_time = None
        if date_str:
            date_str = date_str.strip()
            # Try to parse "16 Mar 2026" or similar
            try:
                publish_time = datetime.strptime(date_str, '%d %b %Y')
            except ValueError:
                pass

        if not publish_time:
            # Try to grab meta dates
            meta_date = response.css('meta[property="article:published_time"]::attr(content)').get()
            if meta_date:
                try:
                    publish_time = datetime.fromisoformat(meta_date.replace('Z', '+00:00')).replace(tzinfo=None)
                except ValueError:
                    pass

        if not publish_time:
            publish_time = datetime.now()

        if publish_time.tzinfo is not None:
            publish_time = publish_time.replace(tzinfo=None)

        if publish_time < self.cutoff_date:
            self.logger.info(f"Reached cutoff date: {publish_time} < {self.cutoff_date}. Closing spider.")
            raise CloseSpider('reached_cutoff_date')

        author = response.css('.author-name::text, [rel="author"]::text').get()
        if author:
            author = author.strip()
        
        # content logic
        paragraphs = response.css('p, .content-wrapper p, .post-content p, .article-content p')
        content_text = ' '.join([p.css('::text').getall() and ' '.join(p.css('::text').getall()).strip() or '' for p in paragraphs])
        # clean extra spaces
        content_text = re.sub(r'\s+', ' ', content_text).strip()

        yield {
            'url': response.url,
            'title': title.strip() if title else 'Untitled',
            'publish_time': publish_time,
            'author': author,
            'content': content_text,
            'language': 'en'
        }

    def errback_httpbin(self, failure):
        if failure.check(HttpError):
            response = failure.value.response
            self.logger.error(f"HttpError on {response.url}: {response.status}")
        elif failure.check(TimeoutError, TCPTimedOutError):
            request = failure.request
            self.logger.error(f"TimeoutError on {request.url}")
