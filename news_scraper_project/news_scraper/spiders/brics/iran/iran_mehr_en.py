# 伊朗mehr en爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
import psycopg2
import time
from datetime import datetime
from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS

class IranMehrEnSpider(scrapy.Spider):
    name = 'iran_mehr_en'
    allowed_domains = ['en.mehrnews.com']
    
    def __init__(self, *args, **kwargs):
        super(IranMehrEnSpider, self).__init__(*args, **kwargs)
        self.target_table = 'iran_mehr_en'
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
            cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            max_date = cur.fetchone()[0]
            cur.close()
            conn.close()

            if self.full_scan:
                return datetime(2026, 1, 1)
            
            if max_date:
                # Incremental mode: only today onwards
                now = datetime.now()
                return datetime(now.year, now.month, now.day)
            
            return datetime(2026, 1, 1)
        except Exception as exc:
            self.logger.error(f"Database init error: {exc}")
            return datetime(2026, 1, 1)

    def start_requests(self):
        # Economy section
        yield scrapy.Request(url="https://en.mehrnews.com/service/economy", callback=self.parse_list)

    def parse_list(self, response):
        # From screenshot 2: <li class="news" ...> <figure> <a href="/news/...">
        news_items = response.css('li.news')
        for news in news_items:
            link = news.css('h3 a::attr(href)').get() or news.css('figure a::attr(href)').get()
            if link:
                full_url = response.urljoin(link)
                yield scrapy.Request(url=full_url, callback=self.parse_detail)

        # Pagination using API endpoint structure 
        # The frontend loads pages using /page/archive.xhtml?mn=130&dt=1&pi=N
        current_page_num = response.meta.get('page_num', 1)
        next_page_num = current_page_num + 1
        next_page_url = f"https://en.mehrnews.com/page/archive.xhtml?mn=130&dt=1&pi={next_page_num}"
        
        yield scrapy.Request(url=next_page_url, callback=self.parse_list, meta={'page_num': next_page_num})

    def parse_detail(self, response):
        item = NewsItem()
        item['url'] = response.url
        item['title'] = response.css('h1.title::text').get('').strip()
        item['author'] = response.css('.item-author span::text').get('Mehr News Agency (English)').strip()
        
        # Content
        content_parts = response.css('.item-text p::text, .item-text div::text').getall()
        item['content'] = '\n'.join([p.strip() for p in content_parts if p.strip()])
        
        # Date parsing
        # Example: Mar 15, 2026, 11:21
        date_str = response.css('.item-date span::text').get('')
        if date_str:
            try:
                # Simplified date parsing for standard English format
                # Mar 15, 2026, 11:21 -> remove extra comma after year if any
                clean_date = date_str.replace(',', '').split() # ['Mar', '15', '2026', '11:21']
                dt_obj = datetime.strptime(' '.join(clean_date[:3]), '%b %d %Y')
                
                if dt_obj < self.cutoff_date:
                    return
                item['publish_time'] = dt_obj
            except Exception as e:
                self.logger.warning(f"Date parsing failed for {response.url}: {e}")
                return
        else:
            return

        item['language'] = 'en'
        item['section'] = 'Economy'
        
        self.item_count += 1
        if self.item_count % 500 == 0:
            self.logger.info(f"Reached {self.item_count} items. Sleeping 20s...")
            time.sleep(20)

        yield item
