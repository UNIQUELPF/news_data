from datetime import datetime

import psycopg2
import scrapy
from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state


class ElnashraSpider(scrapy.Spider):
    """
    Spider for Elnashra (www.elnashra.com) - Lebanon Important News.
    Pagination relies on URL query params `ajax=1&timestamp=LAST_TIMESTAMP&page=NEXT_PAGE`.
    """
    name = "lebanon_elnashra"

    country_code = 'LBN'

    country = '黎巴嫩'
    allowed_domains = ["elnashra.com"]
    use_curl_cffi = True
    target_table = "lebanon_elnashra_news"
    default_cutoff = datetime(2026, 1, 1)

    base_list_url = "https://www.elnashra.com/category/show/important/news/%D8%A3%D8%AE%D8%A8%D8%A7%D8%B1-%D9%85%D9%87%D9%85%D9%91%D8%A9"

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "DOWNLOAD_FAIL_ON_DATALOSS": False
    }

    def __init__(self, full_scan="false", start_date=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_scan = str(full_scan).lower() in ("1", "true", "yes")
        self.cutoff_date = self._init_db_and_get_cutoff()
        
        if start_date:
            try:
                self.cutoff_date = datetime.strptime(str(start_date), "%Y-%m-%d")
                self.logger.info(f"Using custom start_date cutoff: {self.cutoff_date}")
            except ValueError:
                self.logger.warning(f"Invalid start_date '{start_date}'. Using default: {self.cutoff_date}")

    def _init_db_and_get_cutoff(self):
        try:
            conn = psycopg2.connect(**POSTGRES_SETTINGS)
            cur = conn.cursor()
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.target_table} (
                    id SERIAL PRIMARY KEY,
                    url VARCHAR(500) UNIQUE,
                    title VARCHAR(500),
                    content TEXT,
                    publish_time TIMESTAMP,
                    author VARCHAR(255),
                    language VARCHAR(50),
                    section VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

            cur.close()
            conn.close()

            if self.full_scan:
                return self.default_cutoff
            state = get_incremental_state(
                self.settings,
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=self.default_cutoff,
                full_scan=False,
            )
            return max(state["cutoff_date"], self.default_cutoff)
        except Exception as exc:
            self.logger.error(f"DB init failed: {exc}")
            return self.default_cutoff

    def start_requests(self):
        yield scrapy.Request(
            url=self.base_list_url,
            callback=self.parse,
            meta={'page_num': 1}
        )

    def parse(self, response):
        meta = response.meta
        page_num = meta.get('page_num', 1)

        news_items = response.css('li.newsfeed-main:not(.adWrapper)')
        if not news_items:
            self.logger.info("No news items found on list page.")
            return
            
        self.logger.info(f"Loaded list page {page_num} with {len(news_items)} items. URL: {response.url}")

        reached_cutoff = False
        last_timestamp = None

        for item in news_items:
            ts_str = item.xpath('@data-timestamp').get()
            if not ts_str:
                continue
                
            last_timestamp = ts_str
            pub_time = datetime.fromtimestamp(int(ts_str))
            
            if pub_time < self.cutoff_date:
                reached_cutoff = True
                self.logger.debug(f"Reached cutoff {self.cutoff_date} with article from {pub_time} - Stopping")
                continue

            a_tag = item.css('a:not(.notarget)')
            if not a_tag:
                a_tag = item.css('a')
                
            url = a_tag.xpath('@href').get()
            title = a_tag.xpath('@title').get()
            
            if not title:
                title = item.css('h2.topTitle::text').get() or item.css('h3::text').get() or "No Title"

            title = title.strip()
            
            if url:
                url = response.urljoin(url)
                yield scrapy.Request(
                    url,
                    callback=self.parse_article,
                    meta={'pub_time': pub_time, 'title': title, 'url': url},
                    dont_filter=True
                )

        if not reached_cutoff and last_timestamp:
            next_page = page_num + 1
            next_url = f"{self.base_list_url}?ajax=1&timestamp={last_timestamp}&page={next_page}"
            yield scrapy.Request(
                next_url, 
                callback=self.parse, 
                meta={'page_num': next_page},
                dont_filter=True
            )

    def parse_article(self, response):
        meta = response.meta
        
        # Override title with safer detail page title if available
        title = response.css('h1.topTitle::text').get()
        if title:
            title = title.strip()
        else:
            title = meta.get('title', "No Title")

        # Extract content explicitly
        content_blocks = response.css('.articleBody *::text').getall()
        content = " ".join([c.strip() for c in content_blocks if c.strip()])
        
        if not content:
            content = f"[News] {title}"

        news_item = NewsItem(
            url=meta['url'],
            title=title,
            content=content,
            publish_time=meta['pub_time'],
            author="Elnashra",
            language="ar",
            section="Important News"
        )
        yield news_item
