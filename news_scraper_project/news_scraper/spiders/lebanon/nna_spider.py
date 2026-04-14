import json
from datetime import datetime

import psycopg2
import scrapy
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state


class LebanonNnaSpider(scrapy.Spider):
    """
    Spider for National News Agency - Lebanon (nna-leb.gov.lb).
    Uses the backend API endpoint for lists and details.
    Supports full scan (from 2026-01-01) and incremental mode.
    """
    name = "lebanon_nna"

    country_code = 'LBN'

    country = '黎巴嫩'
    allowed_domains = ["nna-leb.gov.lb"]
    target_table = "lebanon_nna_news"
    default_cutoff = datetime(2026, 1, 1)

    # Initial API URL requests page 1
    start_urls = ["https://backend.nna-leb.gov.lb/api/en/news/latest?category_id=4&page=1"]

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

    def parse(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse JSON on {response.url}")
            return

        news_list = data.get("data", {}).get("news", [])
        if not news_list:
            self.logger.info("No news items found in JSON.")
            return

        self.logger.info(f"Loaded page with {len(news_list)} news items. URL: {response.url}")
        
        reached_cutoff = False

        for item in news_list:
            # publish_date is standard unix timestamp in this API
            pub_time_unix = item.get("publish_date")
            if pub_time_unix:
                pub_time = datetime.fromtimestamp(pub_time_unix)
            else:
                pub_time = datetime.now()

            # Cutoff check
            if pub_time < self.cutoff_date:
                self.logger.debug(f"Reached cutoff {self.cutoff_date} with article from {pub_time} - Stopping")
                reached_cutoff = True
                continue

            article_id = item.get("id")
            title = item.get("title", "No Title")
            url = item.get("url", f"https://nna-leb.gov.lb/en/news/short/{article_id}")
            
            url = url.replace('\\/', '/')

            # Request article detail API
            detail_url = f"https://backend.nna-leb.gov.lb/api/en/news/{article_id}"
            
            yield scrapy.Request(
                detail_url,
                callback=self.parse_article,
                meta={'pub_time': pub_time, 'url': url, 'title': title},
                dont_filter=True
            )

        # Pagination using "last_page" from meta
        if not reached_cutoff:
            pagination = data.get("data", {}).get("pagination", {})
            current_page = pagination.get("current_page", 1)
            last_page = pagination.get("last_page", 1)

            if current_page < last_page:
                next_page = current_page + 1
                next_url = f"https://backend.nna-leb.gov.lb/api/en/news/latest?category_id=4&page={next_page}"
                self.logger.info(f"Paginating to page {next_page}")
                yield scrapy.Request(next_url, callback=self.parse, dont_filter=True)

    def parse_article(self, response):
        meta = response.meta
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse article JSON on {response.url}")
            return
            
        article_data = data.get("data", {})
            
        content_html = article_data.get("content", "")
        if content_html:
            soup = BeautifulSoup(content_html, "html.parser")
            content = soup.get_text(separator="\n", strip=True)
        else:
            content = f"[News] {meta['title']}"
            
        news_item = NewsItem(
            url=meta['url'],
            title=meta['title'],
            content=content,
            publish_time=meta['pub_time'],
            author="NNA Lebanon",
            language="en",
            section="Economy"
        )
        yield news_item
