# 阿尔及利亚dzair tube爬虫，负责抓取对应站点、机构或栏目内容。

from datetime import datetime

import dateparser
import psycopg2
import scrapy
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem
from news_scraper.utils import get_incremental_state

# 阿尔及利亚经济类来源
# 站点：Dzair Tube
# 入库表：dza_dzair_tube
# 语言：阿拉伯语


class AlgeriaDzairTubeSpider(scrapy.Spider):
    """阿尔及利亚 Dzair Tube 爬虫。

    抓取站点：https://www.dzair-tube.dz
    抓取栏目：economie
    入库表：dza_dzair_tube
    语言：阿拉伯语
    """

    name = "algeria_dzair_tube"


    country_code = 'DZA'


    country = '阿尔及利亚'
    allowed_domains = ["dzair-tube.dz"]
    # 当前 spider 对应的数据库表名。
    target_table = "dza_dzair_tube"

    # 从经济栏目入口页开始抓取。
    start_urls = [
        "https://www.dzair-tube.dz/economie/",
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
            yield scrapy.Request(url, callback=self.parse_listing, meta={"page": 1})

    def parse_listing(self, response):
        # Dzair Tube 的经济栏目是 WordPress 结构，列表页取文章链接并继续翻页。
        article_links = response.css("h2 a::attr(href)").getall()

        unique_links = []
        for href in article_links:
            full_url = response.urljoin(href)
            if "/economie/page/" in full_url or full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            unique_links.append(full_url)

        for article_url in unique_links:
            yield scrapy.Request(article_url, callback=self.parse_detail)

        if self.reached_cutoff:
            return

        next_page = response.css("a.next.page-numbers::attr(href), link[rel='next']::attr(href)").get()
        if next_page:
            next_page_num = response.meta.get("page", 1) + 1
            yield response.follow(next_page, callback=self.parse_listing, meta={"page": next_page_num})

    def parse_detail(self, response):
        # 详情页提取标题、时间、作者和正文，整理为统一字段。
        title = self._clean_text(response.css("h1::text").get())
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

        author = self._clean_text(response.xpath("//*[contains(text(), 'بقلم:')]/text()").get())
        if "بقلم:" in author:
            author = author.split("بقلم:", 1)[1].strip()
        if not author:
            author = "Dzair Tube"

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = author
        item["language"] = "ar"
        item["section"] = "economie"
        item["scrape_time"] = datetime.now()
        yield item

    def _extract_publish_time(self, response):
        value = response.xpath("//meta[@property='article:published_time']/@content").get()
        if not value:
            value = self._clean_text(" ".join(response.css("article ::text").getall()[:40]))
        if not value:
            return None

        parsed = dateparser.parse(value, languages=["ar", "fr"], settings={"TIMEZONE": "UTC"})
        if not parsed:
            return None
        return parsed.replace(tzinfo=None)

    def _extract_content(self, response):
        # 正文优先走 entry-content，找不到时退回 article 容器。
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one(".entry-content") or soup.select_one("article")
        if not root:
            return ""

        for unwanted in root.select(
            "script, style, nav, footer, header, form, aside, figure, .share, .social, .tags"
        ):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text:
                continue
            if len(text) < 20:
                continue
            if text in parts:
                continue
            parts.append(text)

        if parts:
            return "\n\n".join(parts)

        fallback = response.xpath("//meta[@property='og:description']/@content").get()
        return self._clean_text(fallback)

    def _clean_text(self, value):
        if not value:
            return ""
        return " ".join(value.split()).strip()
