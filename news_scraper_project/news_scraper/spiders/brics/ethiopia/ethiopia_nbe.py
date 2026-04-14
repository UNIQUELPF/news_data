# 埃塞俄比亚nbe爬虫，负责抓取对应站点、机构或栏目内容。

import re
from datetime import datetime

import psycopg2
import scrapy
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state


class EthiopiaNBESpider(scrapy.Spider):
    name = "ethiopia_nbe"

    country_code = 'ETH'

    country = '埃塞俄比亚'
    allowed_domains = ["nbe.gov.et"]
    target_table = "ethi_nbe"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        },
    }

    def __init__(self, *args, **kwargs):
        super(EthiopiaNBESpider, self).__init__(*args, **kwargs)
        self.cutoff_date = self._init_db()
        self.seen_urls = set()
        self.visited_list_pages = set()
        self.logger.info(
            f"Spider initialized. Cutoff date set to: {self.cutoff_date}"
        )

    def _init_db(self):
        try:
            db_settings = POSTGRES_SETTINGS.copy()
            if "database" in db_settings:
                db_settings["dbname"] = db_settings.pop("database")
            elif "db" in db_settings:
                db_settings["dbname"] = db_settings.pop("db")

            conn = psycopg2.connect(**db_settings)
            cur = conn.cursor()

            cur.execute(
                f"""
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
                """
            )
            conn.commit()

            cur.close()
            conn.close()

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
        start_url = "https://nbe.gov.et/all-news/"
        self.visited_list_pages.add(start_url)
        yield scrapy.Request(
            url=start_url,
            callback=self.parse_list,
        )

    def parse_list(self, response):
        links = response.css('a[href*="/nbe_news/"]::attr(href)').getall()
        detail_urls = []
        for link in links:
            full_url = response.urljoin(link)
            if full_url in self.seen_urls:
                continue
            if full_url not in detail_urls:
                detail_urls.append(full_url)

        for detail_url in detail_urls:
            yield scrapy.Request(
                url=detail_url,
                callback=self.parse_article,
            )

        pagination_links = response.css('a.page-numbers::attr(href)').getall()
        for next_link in pagination_links:
            next_url = response.urljoin(next_link)
            if "/all-news/" not in next_url:
                continue
            if next_url in self.visited_list_pages:
                continue
            self.visited_list_pages.add(next_url)
            yield scrapy.Request(next_url, callback=self.parse_list)

    def parse_article(self, response):
        title = response.css("h1::text, .elementor-heading-title::text").get()
        if not title:
            return
        title = title.strip()

        publish_time = self._extract_publish_time(response)
        if not publish_time:
            return

        if publish_time < self.cutoff_date:
            return

        content_parts = response.css(
            ".elementor-widget-theme-post-content p::text, "
            ".entry-content p::text, "
            "main p::text"
        ).getall()
        if not content_parts:
            content_parts = response.xpath(
                '//article//p//text() | //main//p//text()'
            ).getall()

        clean_parts = [part.strip() for part in content_parts if part and part.strip()]
        content = "\n".join(clean_parts)
        if not content:
            return

        language = "am" if self._contains_amharic(title + content) else "en"

        yield {
            "title": title,
            "publish_time": publish_time,
            "author": "National Bank of Ethiopia",
            "content": content,
            "url": response.url,
            "language": language,
            "section": "all-news",
        }

    def _extract_publish_time(self, response):
        meta_date = response.css(
            'meta[property="article:published_time"]::attr(content), '
            'meta[property="og:updated_time"]::attr(content), '
            'time::attr(datetime)'
        ).get()
        if meta_date:
            parsed = self._parse_date_text(meta_date)
            if parsed:
                return parsed.replace(tzinfo=None)

        text_blob = " ".join(
            [text.strip() for text in response.xpath("//text()").getall() if text.strip()]
        )

        patterns = [
            r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},\s*20\d{2}\b",
            r"\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+20\d{2}\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text_blob, re.IGNORECASE)
            if not match:
                continue
            parsed = self._parse_date_text(match.group(0))
            if parsed:
                return parsed.replace(tzinfo=None)
        return None

    @staticmethod
    def _parse_date_text(date_text):
        if not date_text:
            return None

        normalized = date_text.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            pass

        cleaned = re.sub(r"\s+\|.*$", "", normalized).strip()
        formats = [
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _contains_amharic(text):
        return bool(re.search(r"[\u1200-\u137F]", text))
