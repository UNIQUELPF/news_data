# 阿根廷lanacion爬虫，负责抓取对应站点、机构或栏目内容。

from datetime import datetime
from email.utils import parsedate_to_datetime

import psycopg2
import scrapy
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem
from news_scraper.utils import get_incremental_state

# 阿根廷经济类来源
# 站点：La Nacion
# 入库表：arg_lanacion
# 语言：西班牙语


class ArgentinaLaNacionSpider(scrapy.Spider):
    """阿根廷 La Nacion 爬虫。

    抓取站点：https://www.lanacion.com.ar
    抓取入口：Economia RSS
    入库表：arg_lanacion
    语言：西班牙语
    """

    name = "argentina_lanacion"


    country_code = 'ARG'


    country = '阿根廷'
    allowed_domains = ["lanacion.com.ar"]
    # 当前 spider 对应的数据库表名。
    target_table = "arg_lanacion"

    # La Nacion 经济页详情经常被付费墙截断，RSS 正文反而更稳定。
    start_urls = [
        "https://www.lanacion.com.ar/arc/outboundfeeds/rss/category/economia/",
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
            return state["cutoff_date"]
        except Exception as exc:
            self.logger.error(f"DB init failed for {self.target_table}: {exc}")
            return self.default_cutoff

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_feed)

    def parse_feed(self, response):
        # 直接从经济 RSS 读取标题、时间、正文和作者，绕开付费墙干扰。
        for item in response.xpath("//channel/item"):
            url = item.xpath("./link/text()").get()
            if not url or url in self.seen_urls:
                continue
            if "/economia/" not in url:
                continue
            self.seen_urls.add(url)

            publish_time = self._parse_rss_datetime(item.xpath("./pubDate/text()").get())
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue

            title = self._clean_text(item.xpath("./title/text()").get())
            content = self._clean_html(
                item.xpath("./content:encoded/text()", namespaces={"content": "http://purl.org/rss/1.0/modules/content/"}).get()
                or item.xpath("./description/text()").get()
            )
            if not title or not content:
                continue

            author = self._clean_text(
                item.xpath("./dc:creator/text()", namespaces={"dc": "http://purl.org/dc/elements/1.1/"}).get()
            ) or "La Nacion"

            news_item = NewsItem()
            news_item["url"] = url
            news_item["title"] = title
            news_item["content"] = content
            news_item["publish_time"] = publish_time or datetime.now()
            news_item["author"] = author
            news_item["language"] = "es"
            news_item["section"] = "economia"
            news_item["scrape_time"] = datetime.now()
            yield news_item

    def _parse_rss_datetime(self, value):
        if not value:
            return None
        try:
            return parsedate_to_datetime(value).replace(tzinfo=None)
        except Exception:
            return None

    def _clean_html(self, value):
        if not value:
            return ""
        return self._clean_text(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))

    def _clean_text(self, value):
        if not value:
            return ""
        return " ".join(str(value).split()).strip()
