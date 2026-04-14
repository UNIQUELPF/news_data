# 伊朗donya爬虫，负责抓取对应站点、机构或栏目内容。

import time
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import jdatetime
import psycopg2
import scrapy
from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state


class IranDonyaSpider(scrapy.Spider):
    name = 'iran_donya'

    country_code = 'IRN'

    country = '伊朗'
    allowed_domains = ['donya-e-eqtesad.com']
    
    # Persian digits translation table
    PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
    
    def __init__(self, *args, **kwargs):
        super(IranDonyaSpider, self).__init__(*args, **kwargs)
        self.target_table = 'iran_donya'
        self.full_scan = str(kwargs.get('full_scan', 'false')).lower() in ('1', 'true', 'yes')
        self.cutoff_date = self._init_db()
        self.item_count = 0
        self.logger.info(f"Spider initialized. full_scan={self.full_scan}, cutoff date={self.cutoff_date}")

    def _init_db(self):
        try:
            conn = psycopg2.connect(**POSTGRES_SETTINGS)
            cur = conn.cursor()
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.target_table} (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(500),
                    publish_time TIMESTAMP,
                    author VARCHAR(255),
                    content TEXT,
                    url VARCHAR(500) UNIQUE,
                    language VARCHAR(50),
                    section VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            cur.close()
            conn.close()

            if self.full_scan:
                return datetime(2026, 1, 1)

            state = get_incremental_state(
                self.settings,
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=datetime(2026, 1, 1),
                full_scan=False,
            )
            if state["source"] in ("unified", "legacy"):
                now = datetime.now()
                return datetime(now.year, now.month, now.day)
            
            return datetime(2026, 1, 1)
        except Exception as exc:
            self.logger.error(f"Database init error: {exc}")
            return datetime(2026, 1, 1)

    def start_requests(self):
        # Economy section requested by user
        urls = [
            "https://donya-e-eqtesad.com/%D8%A8%D8%AE%D8%B4-%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-183"
        ]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse_list)

    def parse_list(self, response):
        # Extract article links from headers or main container
        links = response.css('h2 a::attr(href)').getall()
        if not links:
            links = response.css('li a[href*="/4"]:not([href*="page="])::attr(href)').getall()
        
        # Filter and join links
        links = list(set([response.urljoin(l) for l in links if '/%D8%A8%D8%AE%D8%B4-' in l or '/42' in l]))
        
        for link in links:
            yield scrapy.Request(url=link, callback=self.parse_detail)

        # Pagination logic based on Fig 1
        next_pages = response.css('footer.service_pagination a::attr(href)').getall()
        current_page_num = self._get_page_num(response.url)
        
        for p_link in next_pages:
            p_url = response.urljoin(p_link)
            p_num = self._get_page_num(p_url)
            if p_num > current_page_num:
                yield scrapy.Request(url=p_url, callback=self.parse_list)
                break 

    def _get_page_num(self, url):
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        try:
            return int(params.get('page', [1])[0])
        except:
            return 1

    def parse_detail(self, response):
        item = NewsItem()
        item['url'] = response.url
        
        # Title
        item['title'] = response.css('h1::text').get('').strip()
        if not item['title']:
            item['title'] = response.xpath('//h1/text()').get('').strip()

        # Date and Author info often in a specific block
        date_str = ""
        header_date_match = response.xpath('//*[contains(text(), "۱۴۰")]/text()').re(r'\d{4}/\d{2}/\d{2}')
        if header_date_match:
            date_str = header_date_match[0]
        
        if date_str:
            publish_time = self._parse_persian_date(date_str)
            if publish_time:
                if publish_time < self.cutoff_date:
                    self.logger.info(f"Article date {publish_time} older than cutoff {self.cutoff_date}. URL: {response.url}")
                    return
                item['publish_time'] = publish_time
            else:
                return
        else:
            # Meta fallback
            meta_date = response.css('meta[property="article:published_time"]::attr(content)').get()
            if meta_date:
                try:
                    publish_time = datetime.fromisoformat(meta_date.replace('Z', '+00:00'))
                    if publish_time.timestamp() < self.cutoff_date.timestamp():
                        return
                    item['publish_time'] = publish_time
                except:
                    pass
            
            if not item.get('publish_time'):
                self.logger.warning(f"Could not parse date for {response.url}")
                return

        # Content
        content_parts = response.css('.news-text p::text, .news-text div::text, .news-text span::text').getall()
        item['content'] = '\n'.join([p.strip() for p in content_parts if p.strip() and len(p.strip()) > 10])
        
        if not item['content']:
             item['content'] = '\n'.join(response.xpath('//div[contains(@class, "news-text")]//text()').getall())
        
        item['author'] = 'Donya-e-Eqtesad'
        item['language'] = 'fa'
        item['section'] = 'Economy'
        
        self.item_count += 1
        if self.item_count % 500 == 0:
            self.logger.info(f"Reached {self.item_count} items. Sleeping 20s...")
            time.sleep(20)
            
        yield item

    def _parse_persian_date(self, date_str):
        try:
            date_str = date_str.translate(self.PERSIAN_DIGITS)
            parts = [int(p) for p in date_str.split('/') if p.strip()]
            if len(parts) != 3:
                return None
            
            sh_year, sh_month, sh_day = parts
            jd = jdatetime.date(sh_year, sh_month, sh_day)
            gregorian_date = jd.togregorian()
            return datetime.combine(gregorian_date, datetime.min.time())
        except Exception as e:
            self.logger.error(f"Error parsing date {date_str}: {e}")
            return None
