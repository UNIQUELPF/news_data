import scrapy
import psycopg2
import logging
from datetime import datetime
import re
from scrapy.exceptions import CloseSpider
import dateparser

class AfricaThePresidencySpider(scrapy.Spider):
    name = 'africa_thepresidency'
    allowed_domains = ['thepresidency.gov.za']
    target_table = 'afr_thepresidency'

    use_curl_cffi = False

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
        super(AfricaThePresidencySpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime(2026, 1, 1)
        self.seen_urls = set()
        
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(AfricaThePresidencySpider, cls).from_crawler(crawler, *args, **kwargs)
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
        url = "https://www.thepresidency.gov.za/speeches-statements-advisories?page=0"
        yield scrapy.Request(url, callback=self.parse_list, cb_kwargs={'page': 0})

    def parse_list(self, response, page):
        articles = response.css('.views-field-title, div.views-row, article, li.views-row')
        if not articles:
            self.logger.info(f"No articles found on page {page}. Stopping.")
            return

        all_old = True
        found_new = False
        
        for article in articles:
            a_elem = article.css('a')
            if not a_elem and article.root.tag == 'a':
                a_elem = [article]
            
            if not a_elem:
                continue
                
            a_elem = a_elem[0]
            link = a_elem.attrib.get('href') or a_elem.css('::attr(href)').get()
            title = a_elem.css('::text').get()
            
            if link and link.startswith('/'):
                link = "https://www.thepresidency.gov.za" + link
                
            title = title.strip() if title else "Unknown Title"
            
            date_str = article.css('time::attr(datetime)').get()
            if not date_str:
                row = article.xpath('ancestor::*[contains(@class, "views-row") or contains(@class, "grid-view") or contains(@class, "item")][1]')
                if row:
                    date_str = row.css('time::attr(datetime)').get()
                
            if not date_str:
                date_el = article.css('.views-field-created .field-content::text, .date::text, .published::text')
                if not date_el:
                    row = article.xpath('ancestor::*[contains(@class, "views-row") or contains(@class, "grid-view")][1]')
                    if row:
                        date_el = row.css('.views-field-created .field-content::text, .date::text, .published::text')
                
                if date_el:
                    date_str = " ".join([d.strip() for d in date_el.getall() if d.strip()])
            
            publish_time = None
            if date_str:
                try:
                    if 'T' in date_str and 'Z' in date_str:
                        date_str = date_str.replace('Z', '+00:00')
                    parsed = dateparser.parse(date_str)
                    if parsed:
                        publish_time = parsed.replace(tzinfo=None)
                except Exception as e:
                    self.logger.error(f"Failed to parse date: {date_str} error: {e}")
            
            if not publish_time:
                publish_time = datetime.now()

            if publish_time >= self.cutoff_date:
                all_old = False
            else:
                continue

            if link not in self.seen_urls:
                found_new = True
                self.seen_urls.add(link)
                
                yield scrapy.Request(
                    link,
                    callback=self.parse_article,
                    cb_kwargs={'title': title, 'publish_time': publish_time}
                )

        if not all_old and len(articles) > 0:
            next_page = page + 1
            next_url = f"https://www.thepresidency.gov.za/speeches-statements-advisories?page={next_page}"
            yield scrapy.Request(next_url, callback=self.parse_list, cb_kwargs={'page': next_page})

    def parse_article(self, response, title, publish_time):
        author = "The Presidency"
        
        paragraphs = response.css('div.field--name-body p, article p, div.content p, .field-content p')
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
