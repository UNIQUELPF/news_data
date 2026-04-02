# 阿尔及利亚bank of algeria爬虫，负责抓取对应站点、机构或栏目内容。

import json
from datetime import datetime

import dateparser
import psycopg2
import scrapy
from bs4 import BeautifulSoup

from news_scraper.items import NewsItem


# 阿尔及利亚政府/监管类来源
# 站点：Bank of Algeria
# 入库表：dza_bank_of_algeria
# 语言：阿拉伯语


class AlgeriaBankOfAlgeriaSpider(scrapy.Spider):
    """阿尔及利亚中央银行爬虫。 政府/官方金融机构

    抓取站点：https://www.bank-of-algeria.dz
    抓取入口：WordPress 分类 API -> Communiqués de presse
    入库表：dza_bank_of_algeria
    语言：法语
    """

    name = "algeria_bank_of_algeria"
    allowed_domains = ["bank-of-algeria.dz", "www.bank-of-algeria.dz"]
    target_table = "dza_bank_of_algeria"

    category_api = "https://www.bank-of-algeria.dz/wp-json/wp/v2/posts?categories=77&per_page=20&page={page}"
    default_cutoff = datetime(2026, 1, 1)

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }

    def __init__(self, full_scan="false", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_scan = str(full_scan).lower() in ("1", "true", "yes")
        self.cutoff_date = self.default_cutoff
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
        yield scrapy.Request(self.category_api.format(page=1), callback=self.parse_api, meta={"page": 1})

    def parse_api(self, response):
        posts = json.loads(response.text)
        if not posts:
            return

        for post in posts:
            title = self._clean_text(post.get("title", {}).get("rendered"))
            url = post.get("link")
            publish_time = self._parse_datetime(post.get("date"))
            content = self._extract_html_content(post.get("content", {}).get("rendered", ""))

            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                self.reached_cutoff = True
                continue
            if not title or not url or not content:
                continue

            item = NewsItem()
            item["url"] = url
            item["title"] = title
            item["content"] = content
            item["publish_time"] = publish_time or datetime.now()
            item["author"] = "Bank of Algeria"
            item["language"] = "fr"
            item["section"] = "communiques-de-presse"
            item["scrape_time"] = datetime.now()
            yield item

        if not self.reached_cutoff:
            next_page = response.meta["page"] + 1
            yield scrapy.Request(self.category_api.format(page=next_page), callback=self.parse_api, meta={"page": next_page})

    def _extract_html_content(self, html):
        soup = BeautifulSoup(html, "html.parser")
        parts = []
        for node in soup.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 12:
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
