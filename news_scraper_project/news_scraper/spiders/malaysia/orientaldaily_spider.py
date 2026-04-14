from datetime import datetime

import psycopg2
import scrapy
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state


class OrientalDailySpider(scrapy.Spider):
    name = "malaysia_orientaldaily"

    country_code = 'MYS'

    country = '马来西亚'
    allowed_domains = ["orientaldaily.com.my"]
    target_table = "malaysia_orientaldaily_news"
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS': 8,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }

    # Business section
    BASE_URL = "https://www.orientaldaily.com.my/news/business?page={page}"

    def __init__(self, start_date=None, *args, **kwargs):
        super(OrientalDailySpider, self).__init__(*args, **kwargs)
        if start_date:
            self.cutoff_date = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            self.cutoff_date = self.get_latest_db_date()
        self.logger.info(f"Using cutoff: {self.cutoff_date}")
        self.init_db()

    def get_latest_db_date(self):
        try:
            conn = psycopg2.connect(**POSTGRES_SETTINGS)
            cur = conn.cursor()
            cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{self.target_table}')")
            if not cur.fetchone()[0]:
                return datetime(2026, 1, 1)

            cur.close()
            conn.close()
            state = get_incremental_state(
                getattr(self, "settings", None),
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=datetime(2026, 1, 1),
                full_scan=False,
            )
            return state["cutoff_date"]
        except Exception as e:
            self.logger.warning(f"Failed to get max date from DB, defaulting to 2026-01-01: {e}")
        return datetime(2026, 1, 1)

    def init_db(self):
        try:
            conn = psycopg2.connect(**POSTGRES_SETTINGS)
            cur = conn.cursor()
            cur.execute(f"CREATE TABLE IF NOT EXISTS {self.target_table} (url TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT, publish_time TIMESTAMP NOT NULL, author VARCHAR(255), language VARCHAR(50), section VARCHAR(100), scraped_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            self.logger.error(f"Failed to init table: {e}")

    def iter_start_requests(self):
        yield scrapy.Request(self.BASE_URL.format(page=1), callback=self.parse_list, meta={'page': 1})

    def start_requests(self):
        yield from self.iter_start_requests()

    async def start(self):
        for request in self.iter_start_requests():
            yield request

    def parse_list(self, response):
        page = response.meta['page']
        
        # Use news-item for more reliable selection
        items = response.css('div.news-item')
        if not items:
            self.logger.info(f"No more items on page {page}")
            return

        self.logger.info(f"Page {page}: found {len(items)} items")
            
        for item in items:
            url = item.css('a.link ::attr(href)').get()
            title = item.css('h3 ::text').get()
            time_str = item.css('time ::attr(datetime)').get()
            
            if not url or not time_str:
                continue

            # Standard format: 2026-03-25 14:39:00
            try:
                dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            except Exception as e:
                self.logger.error(f"Failed to parse time {time_str}: {e}")
                continue

            # Check cutoff early if possible
            if dt < self.cutoff_date:
                self.logger.info(f"Reached date cutoff {self.cutoff_date} at {url} (date: {dt})")
                # Since items are usually chronological, we could potentially stop here.
                # But for robustness we'll just skip this item.
                continue

            yield scrapy.Request(
                url, 
                callback=self.parse_article,
                meta={'title': title, 'publish_time': dt}
            )
            
        # Pagination
        # Oriental Daily has a pagination section. We could use it or just increment if we found items.
        if len(items) > 0:
            next_page = page + 1
            if next_page <= 1000: # Safety cap
                yield scrapy.Request(self.BASE_URL.format(page=next_page), callback=self.parse_list, meta={'page': next_page})

    def parse_article(self, response):
        # Already have some info from meta
        title = response.css('h1 ::text').get() or response.meta.get('title')
        dt = response.meta.get('publish_time')
        
        # Double check date in article (robustness)
        publish_time_meta = response.css('meta[property="article:published_time"]::attr(content)').get()
        if publish_time_meta:
            try:
                # 2026-03-25T14:39:00+08:00
                dt_alt = datetime.fromisoformat(publish_time_meta).replace(tzinfo=None)
                if dt_alt:
                    dt = dt_alt
            except:
                pass

        if dt < self.cutoff_date:
            return

        # Use more precise selection for article content
        # Usually inside //div[contains(@class, 'col-')] or //article
        paragraphs = response.xpath("//div[contains(@class, 'col-')]//p").getall()
        if not paragraphs:
            paragraphs = response.css('p').getall()
            
        valid_paras = []
        skip_keywords = ["WhatsApp Channel", "Follow我們", "马来西亚华人社会的眼中", "点击这里", "创刊于2002年", "檔案照", "档案照", "查看更多", "©"]
        
        for p_html in paragraphs:
            soup_p = BeautifulSoup(p_html, 'html.parser')
            text = soup_p.get_text().strip()
            if not text: continue
            if any(k in text for k in skip_keywords):
                # Stop if we hit a signature paragraph
                if "WhatsApp Channel" in text or "Follow我們" in text:
                    break
                continue
            valid_paras.append(text)
            
        content_text = "\n\n".join(valid_paras).strip()


        # Author
        author = response.css('meta[name="dable:author"]::attr(content)').get() or "東方網"

        item = NewsItem()
        item['title'] = title.strip() if title else "Untitled"
        item['url'] = response.url
        item['publish_time'] = dt.strftime("%Y-%m-%d %H:%M:%S")
        item['author'] = author.strip()
        item['content'] = content_text
        item['section'] = "Finance"
        item['language'] = "zh"
        
        yield item
