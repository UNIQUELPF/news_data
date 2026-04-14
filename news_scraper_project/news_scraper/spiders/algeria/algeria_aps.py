# 阿尔及利亚aps爬虫，负责抓取对应站点、机构或栏目内容。

import re
from datetime import datetime

import dateparser
import psycopg2
import scrapy
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem
from news_scraper.utils import get_incremental_state

# 阿尔及利亚经济类来源
# 站点：APS
# 入库表：dza_aps
# 语言：阿拉伯语


class AlgeriaApsSpider(scrapy.Spider):
    """阿尔及利亚 APS 爬虫。

    抓取站点：https://www.aps.dz
    抓取栏目：经济 -> 银行与金融
    入库表：dza_aps
    语言：阿拉伯语
    """

    name = "algeria_aps"


    country_code = 'DZA'


    country = '阿尔及利亚'
    allowed_domains = ["aps.dz"]
    # 当前 spider 对应的数据库表名。
    target_table = "dza_aps"

    # 从 APS 经济栏目入口开始翻页抓取。
    start_urls = [
        "https://www.aps.dz/economie/banque-et-finances",
    ]

    # 首次抓取的默认时间边界；后续会优先使用数据库里的最新时间做增量。
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
            state = get_incremental_state(
                self.settings,
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=self.default_cutoff,
                full_scan=self.full_scan,
            )
            self.seen_urls = state["scraped_urls"]
            return state["cutoff_date"]
        except Exception as exc:
            self.logger.error(f"DB init failed for {self.target_table}: {exc}")
            return self.default_cutoff

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        # APS 列表页先收集文章链接，再继续找下一页。
        article_links = response.xpath(
            '//a[contains(@href, "/economie/banque-et-finances/")]/@href'
        ).getall()

        unique_links = []
        for href in article_links:
            full_url = response.urljoin(href)
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            unique_links.append(full_url)

        for article_url in unique_links:
            yield scrapy.Request(article_url, callback=self.parse_detail)

        if self.reached_cutoff:
            return

        next_page = response.xpath(
            '//a[contains(@href, "/economie/banque-et-finances?start=")]/@href'
        ).get()
        if next_page:
            yield response.follow(next_page, callback=self.parse_listing)
            return

        pager_links = response.xpath(
            '//a[contains(@href, "/economie/banque-et-finances")]/@href'
        ).getall()
        next_url = self._pick_next_page(response.url, pager_links)
        if next_url:
            yield scrapy.Request(response.urljoin(next_url), callback=self.parse_listing)

    def parse_detail(self, response):
        # 详情页提取标题、时间和正文，组装成统一的 NewsItem。
        title = self._extract_title(response)
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
        item["author"] = "APS"
        item["language"] = "ar"
        item["section"] = "banque-et-finances"
        item["scrape_time"] = datetime.now()
        yield item

    def _extract_title(self, response):
        title = response.css("h1::text").get()
        if title:
            return self._clean_text(title)

        title = response.xpath("//meta[@property='og:title']/@content").get()
        if title:
            return self._clean_text(title.split("|")[0])

        return ""

    def _extract_publish_time(self, response):
        raw_date = response.css("time::text").get()
        if not raw_date:
            raw_date = response.xpath("//meta[@property='article:published_time']/@content").get()
        if not raw_date:
            raw_date = response.xpath(
                "//h1/following::*[self::div or self::p or self::span][1]//text()"
            ).get()

        return self._parse_arabic_date(raw_date)

    def _extract_content(self, response):
        # APS 页面结构并不完全稳定，这里按多个正文容器顺序兜底提取。
        soup = BeautifulSoup(response.text, "html.parser")

        selectors = [
            "article",
            "main article",
            "[itemprop='articleBody']",
            ".article-content",
            ".item-content",
            ".entry-content",
            ".post-content",
            ".content",
            "main",
        ]

        root = None
        for selector in selectors:
            root = soup.select_one(selector)
            if root and root.get_text(" ", strip=True):
                break

        if not root:
            root = soup.body
        if not root:
            return ""

        for unwanted in root.select(
            "script, style, nav, footer, header, form, aside, .related, .social, .share"
        ):
            unwanted.decompose()

        title = self._extract_title(response)
        title_text = self._clean_text(title)

        paragraphs = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text:
                continue
            if text == title_text:
                continue
            if text.lower() in ("related articles", "follow us", "most read"):
                continue
            if len(text) < 15:
                continue
            if text not in paragraphs:
                paragraphs.append(text)

        if paragraphs:
            return "\n\n".join(paragraphs)

        meta_desc = response.xpath("//meta[@property='og:description']/@content").get()
        if not meta_desc:
            meta_desc = response.xpath("//meta[@name='description']/@content").get()
        return self._clean_text(meta_desc or "")

    def _pick_next_page(self, current_url, hrefs):
        current_start = self._extract_start_offset(current_url)
        candidates = []

        for href in hrefs:
            start = self._extract_start_offset(href)
            if start is None:
                continue
            if start > current_start:
                candidates.append((start, href))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def _extract_start_offset(self, url):
        match = re.search(r"[?&]start=(\d+)", url or "")
        if match:
            return int(match.group(1))
        return 0 if "banque-et-finances" in (url or "") else None

    def _parse_arabic_date(self, value):
        if not value:
            return None

        iso_match = re.search(
            r"(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})(?::(\d{2}))?",
            value,
        )
        if iso_match:
            year, month, day, hour, minute, second = iso_match.groups()
            return datetime(
                int(year),
                int(month),
                int(day),
                int(hour),
                int(minute),
                int(second or 0),
            )

        parsed = dateparser.parse(
            self._clean_text(value),
            languages=["ar", "fr"],
            settings={"TIMEZONE": "UTC"},
        )
        if not parsed:
            return None
        return parsed.replace(tzinfo=None)

    def _clean_text(self, value):
        if not value:
            return ""
        value = re.sub(r"\s+", " ", value)
        return value.strip()
