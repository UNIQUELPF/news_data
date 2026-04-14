# 伊朗presstv爬虫，负责抓取对应站点、机构或栏目内容。

import time
from datetime import datetime

import psycopg2
import scrapy
from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state


class IranPresstvSpider(scrapy.Spider):
    name = 'iran_presstv'

    country_code = 'IRN'

    country = '伊朗'
    allowed_domains = ['presstv.ir']
    
    def __init__(self, *args, **kwargs):
        super(IranPresstvSpider, self).__init__(*args, **kwargs)
        self.target_table = 'iran_presstv'
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
                max_date = state["cutoff_date"]
                return datetime(max_date.year, max_date.month, max_date.day)

            return datetime(2026, 1, 1)
            
        except Exception as exc:
            self.logger.error(f"Database init error: {exc}")
            return datetime(2026, 1, 1)

    def start_requests(self):
        # Initial page URL for Economy section
        yield scrapy.Request(
            url="https://www.presstv.ir/Section/10102/1", 
            callback=self.parse_list,
            meta={'page_num': 1}
        )

    def parse_list(self, response):
        # Extract all detail links
        links = response.css('a[href*="/Detail/"]::attr(href)').getall()
        # Clean and get unique links
        links = list(set([response.urljoin(l) for l in links if '/Detail/' in l]))
        
        for link in links:
            yield scrapy.Request(url=link, callback=self.parse_detail)

        # Pagination logic
        current_page_num = response.meta.get('page_num', 1)
        next_page_num = current_page_num + 1
        
        # We try to keep fetching the next page unless we hit our cutoff in items or no more valid articles
        # This will gracefully finish based on dates in parse_detail
        next_page_url = f"https://www.presstv.ir/Section/10102/{next_page_num}"
        yield scrapy.Request(
            url=next_page_url, 
            callback=self.parse_list,
            meta={'page_num': next_page_num},
            dont_filter=True
        )

    def parse_detail(self, response):
        item = NewsItem()
        item['url'] = response.url
        
        # Title can be in <title> or h1
        item['title'] = response.css('title::text').get('').strip()
        if not item['title'] or 'PressTV' in item['title']:
            alt_title = response.css('h1::text, .title::text').get()
            if alt_title:
                item['title'] = alt_title.strip()
                
        # Remove site name suffix from title if exists
        item['title'] = item['title'].split(' - PressTV')[0].strip()

        # Content parsing
        content_parts = response.xpath("//div[contains(@class, 'body')]//p//text()").getall()
        if not content_parts:
            content_parts = response.css('.detail-body p::text, article p::text').getall()
            
        item['content'] = '\n'.join([p.strip() for p in content_parts if p.strip() and len(p.strip()) > 5])
        
        # Date parsing
        # Ex: <meta name='DC.Date.Created'  content='3/9/2026 11:50:13 AM'/>
        date_str = response.xpath("//meta[@name='DC.Date.Created']/@content").get()
        if not date_str:
            date_str = response.xpath("//meta[@name='date']/@content").get()
            
        if date_str:
            try:
                # Format: 3/9/2026 11:50:13 AM
                dt_obj = datetime.strptime(date_str, '%m/%d/%Y %I:%M:%S %p')
                if dt_obj < self.cutoff_date:
                    self.logger.info(f"Article {dt_obj} before cutoff {self.cutoff_date}, stopping deeper parse.")
                    return
                item['publish_time'] = dt_obj
            except Exception as e:
                self.logger.warning(f"Date formatting failed: {date_str} - error {e}")
                return
        else:
            self.logger.warning(f"No date found for {response.url}")
            return

        item['author'] = 'Press TV'
        item['language'] = 'en'
        item['section'] = 'Economy'
        
        self.item_count += 1
        if self.item_count % 500 == 0:
            self.logger.info(f"Reached {self.item_count} items. Sleeping 20s...")
            time.sleep(20)

        yield item
