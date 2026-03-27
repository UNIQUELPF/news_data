from datetime import datetime

import dateparser
import psycopg2
import scrapy
from bs4 import BeautifulSoup

from news_scraper.items import NewsItem


# 阿尔及利亚政府/监管类来源
# 站点：COSOB
# 入库表：dza_cosob
# 语言：法语


class AlgeriaCosobSpider(scrapy.Spider):
    """阿尔及利亚证券监管机构 COSOB 爬虫。 政府/官方监管机构

    抓取站点：https://cosob.dz
    抓取栏目：Actualités
    入库表：dza_cosob
    语言：法语
    """

    name = "algeria_cosob"
    allowed_domains = ["cosob.dz"]
    target_table = "dza_cosob"

    start_urls = [
        "https://cosob.dz/category/actualites/",
    ]

    default_cutoff = datetime(2026, 1, 1)

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }

    def __init__(self, full_scan="false", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_scan = str(full_scan).lower() in ("1", "true", "yes")
        self.cutoff_date = self.default_cutoff
        self.seen_urls = set()
        self.reached_cutoff = False

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider.cutoff_date = spider._init_db_and_get_cutoff()
        return spider

    def _init_db_and_get_cutoff(self):
        settings = self.settings.get("POSTGRES_SETTINGS", {})
        if not settings:
            return self.default_cutoff

        try:
            conn = psycopg2.connect(
                dbname=settings["dbname"],
                user=settings["user"],
                password=settings["password"],
                host=settings["host"],
                port=settings["port"],
            )
            cur = conn.cursor()
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.target_table} (
                    id SERIAL PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    content TEXT,
                    publish_time TIMESTAMP,
                    author TEXT,
                    language TEXT,
                    section TEXT,
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
            return max_time
        except Exception as exc:
            self.logger.error(f"DB init failed for {self.target_table}: {exc}")
            return self.default_cutoff

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        article_links = response.css("article a::attr(href), .rtin-item a::attr(href), .entry-title a::attr(href)").getall()

        for href in article_links:
            full_url = response.urljoin(href)
            if (
                full_url in self.seen_urls
                or "/category/" in full_url
                or "/author/" in full_url
                or "/wp-content/uploads/" in full_url
                or full_url.lower().endswith(".pdf")
            ):
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail)

        if self.reached_cutoff:
            return

        next_page = response.css("a.next.page-numbers::attr(href), a[rel='next']::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse_listing)

    def parse_detail(self, response):
        if not isinstance(response, scrapy.http.TextResponse):
            return

        title = self._clean_text(response.css("h1::text").get() or response.xpath("//meta[@property='og:title']/@content").get())
        if not title:
            return

        publish_time = self._extract_publish_time(response)
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            self.reached_cutoff = True
            return

        content = self._extract_content(response, title)
        if not content:
            return

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = "COSOB"
        item["language"] = "fr"
        item["section"] = "actualites"
        item["scrape_time"] = datetime.now()
        yield item

    def _extract_publish_time(self, response):
        value = response.xpath("//meta[@property='article:published_time']/@content").get()
        if not value:
            value = self._clean_text(" ".join(response.css("article ::text").getall()[:40]))
        return self._parse_datetime(value)

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one(".entry-content") or soup.select_one("article")
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, figure, .share"):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 12:
                continue
            if text == title:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)

    def _parse_datetime(self, value):
        if not value:
            return None
        parsed = dateparser.parse(value, languages=["fr"], settings={"TIMEZONE": "UTC"})
        if not parsed:
            return None
        return parsed.replace(tzinfo=None)

    def _clean_text(self, value):
        if not value:
            return ""
        return " ".join(str(value).split()).strip()
