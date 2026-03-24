import scrapy
import psycopg2
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from scrapy.http import FormRequest

from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS

class SaudiMcSpider(scrapy.Spider):
    """
    Spider for Saudi Ministry of Commerce (mc.gov.sa).
    Uses ASP.NET FormRequest via __doPostBack for pagination.
    Supports full scan (from 2026-01-01) and incremental mode.
    """
    name = "saudi_mc"
    allowed_domains = ["mc.gov.sa"]
    start_urls = ["https://mc.gov.sa/en/mediacenter/News/Pages/default.aspx"]
    
    target_table = "saudi_mc_news"
    default_cutoff = datetime(2026, 1, 1)

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

            cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            max_time = cur.fetchone()[0]
            cur.close()
            conn.close()

            if self.full_scan or not max_time:
                return self.default_cutoff
            if max_time.tzinfo is not None:
                max_time = max_time.replace(tzinfo=None)
            return max(max_time, self.default_cutoff)
        except Exception as exc:
            self.logger.error(f"DB init failed: {exc}")
            return self.default_cutoff

    def _parse_datetime(self, text):
        if not text:
            return None
        text = str(text).strip()
        # Common formats: "25 Dec 2025"
        for fmt in ("%d %b %Y", "%d %B %Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    def parse(self, response):
        news_items = response.css('div.newsListItem')
        self.logger.info(f"Loaded page with {len(news_items)} news items. URL: {response.url}")

        if not news_items:
            self.logger.info("No news items found on this page. Stopping.")
            return

        reached_cutoff = False

        for item in news_items:
            # Extract date
            date_str_raw = item.css('[class*="date"] *::text, [class*="Date"] *::text, [class*="date"]::text, [class*="Date"]::text').getall()
            date_str = " ".join(date_str_raw).replace("\r", " ").replace("\n", " ").strip()
            pub_time = self._parse_datetime(date_str)
            self.logger.info(f"Parsed Date: {date_str} -> {pub_time}")
            if not pub_time:
                pub_time = datetime.now()

            if pub_time < self.cutoff_date:
                self.logger.debug(f"Reached cutoff {self.cutoff_date} with article from {pub_time} - Stopping")
                reached_cutoff = True
                continue

            # Extract link
            link = item.css('a::attr(href)').get()
            if not link:
                continue

            article_url = response.urljoin(link)
            yield scrapy.Request(
                article_url,
                callback=self.parse_article,
                meta={'pub_time': pub_time}
            )

        # Pagination using __doPostBack mechanism natively solved by Scrapy's FormRequest
        if not reached_cutoff:
            next_link = response.xpath('//a[contains(@class, "Next") or contains(text(), "Next")]/@href').get()
            if next_link and "__doPostBack" in next_link:
                match = re.search(r"__doPostBack\('(.*?)',''\)", next_link)
                if match:
                    event_target = match.group(1)
                    self.logger.info(f"Paginating to next page via event target: {event_target}")
                    yield FormRequest.from_response(
                        response,
                        formdata={
                            '__EVENTTARGET': event_target,
                            '__EVENTARGUMENT': ''
                        },
                        callback=self.parse,
                        dont_filter=True
                    )

    def parse_article(self, response):
        pub_time = response.meta['pub_time']
        
        # Scrapy responses handles HTML fine, using bs4 to parse complex structures cleanly
        soup = BeautifulSoup(response.body, 'html.parser')
        
        # Extract title
        h1 = soup.find('h1')
        title = h1.text.strip() if h1 else 'No Title'
        
        # Extract content
        content_div = soup.find('div', class_='ms-rtestate-field') or soup.find(id=lambda x: x and 'newsInner' in x)
        content = content_div.get_text(separator='\\n', strip=True) if content_div else f"[News] {title}"
        
        news_item = NewsItem(
            url=response.url,
            title=title,
            content=content,
            publish_time=pub_time,
            author="Ministry of Commerce",
            language="en",
            section="News"
        )
        yield news_item
