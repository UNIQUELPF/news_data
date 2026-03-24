import json
import logging
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import scrapy
import psycopg2
import html

from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS

class EntarabiSpider(scrapy.Spider):
    """
    Spider for Entarabi.com (Saudi Arabia).
    Uses the WordPress REST API for robust pagination and data extraction.
    Supports full scan (from 2026-01-01) and incremental mode.
    """
    name = "saudi_entarabi"
    allowed_domains = ["entarabi.com"]
    target_table = "saudi_entarabi_news"
    default_cutoff = datetime(2026, 1, 1)

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
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
            # Ensure max_time is timezone-naive for comparison
            if max_time.tzinfo is not None:
                max_time = max_time.replace(tzinfo=None)
            return max(max_time, self.default_cutoff)
        except Exception as exc:
            self.logger.error(f"DB init failed: {exc}")
            return self.default_cutoff

    def start_requests(self):
        url = "https://entarabi.com/wp-json/wp/v2/posts?page=1&per_page=100&_embed=1"
        yield scrapy.Request(
            url=url,
            callback=self.parse_api_page,
            meta={'page': 1},
            dont_filter=True
        )

    def parse_api_page(self, response):
        if response.status == 400:
            self.logger.info("Reached the end of pagination (400 Bad Request).")
            return

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error("Failed to parse JSON response.")
            return

        if not isinstance(data, list) or not data:
            self.logger.info("No items in response or not a list. Stopping.")
            return

        self.logger.info(f"Page {response.meta['page']} loaded {len(data)} items.")
        reached_cutoff = False

        for item in data:
            # Title
            title_html = item.get("title", {}).get("rendered", "")
            title = html.unescape(title_html).strip() if title_html else "No Title"

            # URL
            article_url = item.get("link")

            # Publish time
            date_str = item.get("date")  # Format: "2026-03-23T23:59:51"
            pub_time = None
            if date_str:
                try:
                    pub_time = datetime.fromisoformat(date_str)
                    if pub_time.tzinfo is not None:
                        pub_time = pub_time.replace(tzinfo=None)
                except ValueError:
                    pass
            if not pub_time:
                pub_time = datetime.now()

            # Check cutoff logic
            if pub_time < self.cutoff_date:
                self.logger.debug(f"Reached cutoff {self.cutoff_date} with article from {pub_time} - Stopping")
                reached_cutoff = True
                continue

            # Content
            content_html = item.get("content", {}).get("rendered", "")
            if content_html:
                soup = BeautifulSoup(content_html, "html.parser")
                content = soup.get_text(separator="\n", strip=True)
            else:
                content = ""

            # Extract category from _embedded
            section = "عام"
            embedded = item.get("_embedded", {})
            terms = embedded.get("wp:term", [])
            for term_group in terms:
                for term in term_group:
                    if term.get("taxonomy") == "category":
                        section = html.unescape(term.get("name", "عام"))
                        break
                if section != "عام":
                    break

            # Extract author
            author = "فريق إنت عربي"
            authors = embedded.get("author", [])
            if authors and len(authors) > 0:
                author_name = authors[0].get("name")
                if author_name:
                    author = html.unescape(author_name)

            news_item = NewsItem(
                url=article_url,
                title=title,
                content=content,
                publish_time=pub_time,
                author=author,
                language="ar",
                section=section
            )
            yield news_item

        # Go to next page if cutoff is not reached
        if not reached_cutoff:
            next_page = response.meta['page'] + 1
            next_url = f"https://entarabi.com/wp-json/wp/v2/posts?page={next_page}&per_page=100&_embed=1"
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_api_page,
                meta={'page': next_page},
                dont_filter=True
            )
