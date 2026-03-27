import json
from datetime import datetime

import dateparser
import psycopg2
import scrapy

from news_scraper.items import NewsItem


# 阿根廷经济类来源
# 站点：Ambito
# 入库表：arg_ambito
# 语言：西班牙语


class ArgentinaAmbitoSpider(scrapy.Spider):
    """阿根廷 Ambito 爬虫。

    抓取站点：https://www.ambito.com
    抓取栏目：economia / finanzas
    入库表：arg_ambito
    语言：西班牙语
    """

    name = "argentina_ambito"
    allowed_domains = ["ambito.com"]
    # 当前 spider 对应的数据库表名。
    target_table = "arg_ambito"

    # 从经济栏目入口页开始抓取。
    start_urls = [
        "https://www.ambito.com/economia",
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
        # Ambito 列表页里只保留经济和金融相关详情页链接。
        article_links = response.css("h2 a::attr(href)").getall()

        for href in article_links:
            full_url = response.urljoin(href)
            if full_url in self.seen_urls:
                continue
            if "/economia/" not in full_url and "/finanzas/" not in full_url:
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        # Ambito 详情页优先使用 JSON-LD 里的 NewsArticle 数据，稳定性更高。
        data = self._extract_article_schema(response)

        title = ""
        content = ""
        publish_time = None
        author = "Ambito"
        section = "economia"

        if data:
            title = self._clean_text(data.get("headline") or data.get("name"))
            content = self._clean_text(data.get("articleBody"))
            publish_time = self._parse_datetime(data.get("datePublished"))

            author_data = data.get("author")
            if isinstance(author_data, dict):
                author = self._clean_text(author_data.get("name")) or author
            elif isinstance(author_data, list) and author_data:
                names = []
                for entry in author_data:
                    if isinstance(entry, dict) and entry.get("name"):
                        names.append(self._clean_text(entry["name"]))
                if names:
                    author = ", ".join(names)

            section = self._clean_text(data.get("articleSection")) or section

        if not title:
            title = self._clean_text(response.css("h1::text").get())
        if not content:
            content = self._clean_text(response.xpath("//meta[@property='og:description']/@content").get())
        if not publish_time:
            publish_time = self._parse_datetime(response.xpath("//meta[@name='last-modified']/@content").get())

        if not title or not content:
            return

        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = author
        item["language"] = "es"
        item["section"] = section
        item["scrape_time"] = datetime.now()
        yield item

    def _extract_article_schema(self, response):
        # 从页面里的 JSON-LD 中提取 NewsArticle 结构化数据。
        for raw in response.css('script[type="application/ld+json"]::text').getall():
            raw = raw.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception:
                continue

            candidates = parsed if isinstance(parsed, list) else [parsed]
            for candidate in candidates:
                if candidate.get("@type") == "NewsArticle":
                    return candidate
        return None

    def _parse_datetime(self, value):
        if not value:
            return None
        parsed = dateparser.parse(value, languages=["es"], settings={"TIMEZONE": "UTC"})
        if not parsed:
            return None
        return parsed.replace(tzinfo=None)

    def _clean_text(self, value):
        if not value:
            return ""
        return " ".join(str(value).split()).strip()
