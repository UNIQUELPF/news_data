import scrapy
from datetime import datetime, timedelta
import psycopg2
import logging
import json
from scrapy.exceptions import CloseSpider
import re

class AfricaBusinessDaySpider(scrapy.Spider):
    name = 'africa_businessday'
    allowed_domains = ['businessday.co.za']
    target_table = 'afr_businessday'

    custom_settings = {
        'CLOSESPIDER_ITEMCOUNT': 550,
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
        super(AfricaBusinessDaySpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime(2026, 1, 1)
        self.seen_urls = set()
        
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(AfricaBusinessDaySpider, cls).from_crawler(crawler, *args, **kwargs)
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
        # We use sitemap index and section indices to reliably pull everything
        urls = [
            'https://www.businessday.co.za/arc/outboundfeeds/sitemap-news-index/',
            'https://www.businessday.co.za/arc/outboundfeeds/sitemap-section-index/',
            'https://www.businessday.co.za/arc/outboundfeeds/sitemap-index/'
        ]
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_sitemap_index,
                headers={'User-Agent': 'Mozilla/5.0'}
            )

    def parse_sitemap_index(self, response):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.body, 'xml')
        sitemap_urls = [loc.text for loc in soup.find_all('loc')]
        
        for url in sitemap_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_sitemap,
                headers={'User-Agent': 'Mozilla/5.0'},
                dont_filter=True
            )

    def parse_sitemap(self, response):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.body, 'xml')
        urls_to_process = []
        
        for url_node in soup.find_all('url'):
            loc = url_node.find('loc')
            lastmod_node = url_node.find('lastmod')
            
            if not loc:
                continue
            
            link = loc.text.strip()
            
            # Simple pre-filter for articles based on URL format
            if '/search/?' in link or '/author/' in link:
                continue
            
            if lastmod_node:
                date_str = lastmod_node.text.strip()
                try:
                    mod_time = datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=None)
                    if mod_time < self.cutoff_date:
                        continue
                except Exception:
                    pass

            urls_to_process.append(link)

        for link in set(urls_to_process):
            if link not in self.seen_urls:
                self.seen_urls.add(link)
                yield scrapy.Request(
                    link, 
                    callback=self.parse_article,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )

    def parse_article(self, response):
        title = response.css('h1::text').get()
        if not title:
            title = response.css('title::text').get()

        publish_time = None
        meta_date = response.css('meta[property="article:published_time"]::attr(content)').get()
        
        if meta_date:
            try:
                publish_time = datetime.fromisoformat(meta_date.replace('Z', '+00:00')).replace(tzinfo=None)
            except Exception:
                pass
                
        if not publish_time:
            import json
            for script in response.css('script[type="application/ld+json"]::text').getall():
                try:
                    data = json.loads(script)
                    date_val = data.get('datePublished') or data.get('dateModified')
                    if date_val:
                        publish_time = datetime.fromisoformat(date_val.replace('Z', '+00:00')).replace(tzinfo=None)
                        break
                except Exception:
                    pass

        if not publish_time:
            publish_time = datetime.now()

        if publish_time.tzinfo is not None:
            publish_time = publish_time.replace(tzinfo=None)

        # Do not use CloseSpider because it exits the whole spider if we just hit one old sidebar link. 
        # Since sitemap is comprehensive, we just ignore this item.
        if publish_time < self.cutoff_date:
            return

        author = response.css('meta[name="author"]::attr(content)').get()
        if not author:
            author = response.css('.c-article-byline__author::text, [rel="author"]::text').get()
        if author:
            author = author.strip()
        
        paragraphs = response.css('.c-article-content p, .b-article-body p, article p')
        if not paragraphs:
            return
            
        content_text = ' '.join([p.css('::text').getall() and ' '.join(p.css('::text').getall()).strip() or '' for p in paragraphs])
        
        import re
        content_text = re.sub(r'\s+', ' ', content_text).strip()

        if not content_text:
            return

        yield {
            'url': response.url,
            'title': title.strip() if title else 'Untitled',
            'publish_time': publish_time,
            'author': author,
            'content': content_text,
            'language': 'en'
        }
