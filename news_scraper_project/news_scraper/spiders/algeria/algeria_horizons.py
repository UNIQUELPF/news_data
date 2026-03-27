from datetime import datetime

import dateparser
import psycopg2
import scrapy
from bs4 import BeautifulSoup

from news_scraper.items import NewsItem


# 阿尔及利亚经济类来源
# 站点：Horizons
# 入库表：dza_horizons
# 语言：法语


class AlgeriaHorizonsSpider(scrapy.Spider):
    """阿尔及利亚 Horizons 爬虫。

    抓取站点：https://www.horizons.dz
    抓取栏目：Economie
    入库表：dza_horizons
    语言：法语
    """

    name = "algeria_horizons"
    allowed_domains = ["horizons.dz"]
    # 当前 spider 对应的数据库表名。
    target_table = "dza_horizons"

    # 从经济栏目入口页开始抓取。
    start_urls = [
        "https://www.horizons.dz/category/economie/",
    ]

    # 首次抓取的默认时间边界；后续优先按数据库里最新时间做增量。
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
        # 初始化目标表，并读取当前表里的最大发布时间作为增量抓取边界。
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
        # Horizons 是典型 WordPress 栏目页，先抓文章链接，再跟进分页。
        article_links = response.css("h2.entry-title a::attr(href), a.more-link::attr(href)").getall()

        unique_links = []
        for href in article_links:
            full_url = response.urljoin(href)
            if "/category/" in full_url or full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            unique_links.append(full_url)

        for article_url in unique_links:
            yield scrapy.Request(article_url, callback=self.parse_detail)

        if self.reached_cutoff:
            return

        next_page = response.css("a.next.page-numbers::attr(href), link[rel='next']::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse_listing)

    def parse_detail(self, response):
        # 详情页提取标题、时间和正文，过滤空内容后入库。
        title = self._clean_text(response.css("h1.entry-title::text").get())
        if not title:
            title = self._clean_text(response.xpath("//meta[@property='og:title']/@content").get())
        if not title:
            return

        publish_time = self._extract_publish_time(response)
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            self.reached_cutoff = True
            return

        content = self._extract_content(response)
        if not content:
            return

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = "Horizons"
        item["language"] = "fr"
        item["section"] = "economie"
        item["scrape_time"] = datetime.now()
        yield item

    def _extract_publish_time(self, response):
        value = response.xpath("//meta[@property='article:published_time']/@content").get()
        if not value:
            value = response.css("time::attr(datetime), time::text").get()
        if not value:
            value = response.css(".entry-date::text, .post-date::text").get()

        if not value:
            return None

        parsed = dateparser.parse(value, languages=["fr"], settings={"TIMEZONE": "UTC"})
        if not parsed:
            return None
        return parsed.replace(tzinfo=None)

    def _extract_content(self, response):
        # 正文优先从 WordPress 常见容器中提取，再用描述信息兜底。
        soup = BeautifulSoup(response.text, "html.parser")
        root = (
            soup.select_one(".entry-content")
            or soup.select_one(".post-content")
            or soup.select_one("article")
        )
        if not root:
            return ""

        for unwanted in root.select(
            "script, style, nav, footer, header, form, aside, .sharedaddy, .jp-relatedposts"
        ):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text:
                continue
            if text.lower() in ("veuillez vous identifier", "lire la suite »"):
                continue
            if len(text) < 20:
                continue
            if text not in parts:
                parts.append(text)

        if parts:
            return "\n\n".join(parts)

        fallback = response.xpath("//meta[@property='og:description']/@content").get()
        return self._clean_text(fallback)

    def _clean_text(self, value):
        if not value:
            return ""
        return " ".join(value.split()).strip()
