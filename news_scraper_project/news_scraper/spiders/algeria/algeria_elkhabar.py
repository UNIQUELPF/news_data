# 阿尔及利亚elkhabar爬虫，负责抓取对应站点、机构或栏目内容。

import re
from datetime import datetime

import dateparser
import psycopg2
import scrapy
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem
from news_scraper.utils import get_incremental_state

# 阿尔及利亚经济类来源
# 站点：El Khabar
# 入库表：dza_elkhabar
# 语言：阿拉伯语


class AlgeriaElkhabarSpider(scrapy.Spider):
    """阿尔及利亚 El Khabar 爬虫。

    抓取站点：https://www.elkhabar.com
    抓取栏目：economie
    入库表：dza_elkhabar
    语言：阿拉伯语
    """

    name = "algeria_elkhabar"


    country_code = 'DZA'


    country = '阿尔及利亚'
    allowed_domains = ["elkhabar.com"]
    # 当前 spider 对应的数据库表名。
    target_table = "dza_elkhabar"

    # 从经济栏目入口页开始翻页抓取。
    start_urls = [
        "https://www.elkhabar.com/economie",
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
        # El Khabar 栏目页通过 ?page=N 分页，列表里只保留经济文章详情链接。
        article_links = response.css('a[href*="/economie/"]::attr(href)').getall()

        unique_links = []
        for href in article_links:
            full_url = response.urljoin(href)
            if full_url.rstrip("/") == "https://www.elkhabar.com/economie":
                continue
            if "?page=" in full_url or full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            unique_links.append(full_url)

        for article_url in unique_links:
            yield scrapy.Request(article_url, callback=self.parse_detail)

        if self.reached_cutoff:
            return

        current_page = response.meta.get("page", 1)
        next_page = current_page + 1
        next_url = f"https://www.elkhabar.com/economie?page={next_page}"
        if response.css(f'a[href="/economie?page={next_page}"]'):
            yield scrapy.Request(next_url, callback=self.parse_listing, meta={"page": next_page})

    def parse_detail(self, response):
        # 详情页提取标题、时间、作者和正文，再统一组装为 NewsItem。
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

        author = self._clean_text(response.css('a[href*="/profile/"]::text').get()) or "El Khabar"

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
        text = self._clean_text(" ".join(response.css("article ::text").getall()[:80]))
        match = re.search(r"\d{2}/\d{2}/\d{4}\s*-\s*\d{2}:\d{2}", text)
        if not match:
            match = re.search(r"\d{2}/\d{2}/\d{4}", text)
        if not match:
            return None

        parsed = dateparser.parse(match.group(0), languages=["ar", "fr"])
        if not parsed:
            return None
        return parsed.replace(tzinfo=None)

    def _extract_content(self, response):
        # 正文以 article 容器为主，并主动清理分享按钮、广告等噪音节点。
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article")
        if not root:
            return ""

        for unwanted in root.select(
            "script, style, nav, footer, header, form, aside, figure, video, .share, .social, .tags, .ads"
        ):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text:
                continue
            if len(text) < 20:
                continue
            if any(token in text for token in ["Facebook", "Twitter", "Messenger", "Telegram", "WhatsApp", "LinkedIn", "Instagram", "TikTok"]):
                continue
            if text in parts:
                continue
            parts.append(text)

        if parts:
            return "\n\n".join(parts)

        fallback = response.xpath("//meta[@property='og:description']/@content").get()
        if not fallback:
            fallback = response.xpath("//meta[@name='description']/@content").get()
        return self._clean_text(fallback)

    def _clean_text(self, value):
        if not value:
            return ""
        return " ".join(value.split()).strip()
