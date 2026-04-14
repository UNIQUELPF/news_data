# 阿根廷pagina12爬虫，负责抓取对应站点、机构或栏目内容。

import json
import re
from datetime import datetime

import dateparser
import psycopg2
import scrapy
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem
from news_scraper.utils import get_incremental_state

# 阿根廷经济类来源
# 站点：Pagina12
# 入库表：arg_pagina12
# 语言：西班牙语


class ArgentinaPagina12Spider(scrapy.Spider):
    """阿根廷 Pagina 12 爬虫。

    抓取站点：https://www.pagina12.com.ar
    抓取栏目：economia
    入库表：arg_pagina12
    语言：西班牙语
    """

    name = "argentina_pagina12"


    country_code = 'ARG'


    country = '阿根廷'
    allowed_domains = ["pagina12.com.ar"]
    # 当前 spider 对应的数据库表名。
    target_table = "arg_pagina12"

    # 从经济栏目入口页开始抓取。
    start_urls = [
        "https://www.pagina12.com.ar/economia/",
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
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        # Pagina 12 的经济页里会混出其他文章，这里先抓年份型详情链接。
        article_links = response.css('a[href^="/2026/"]::attr(href), a[href^="/2025/"]::attr(href)').getall()

        for href in article_links:
            full_url = response.urljoin(href)
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        # 详情页再做一次经济频道过滤，避免混入非经济稿件。
        if 'https://www.pagina12.com.ar/economia' not in response.text:
            return

        title = ""
        description = self._clean_text(response.xpath("//meta[@property='og:description']/@content").get())
        publish_time = None
        author = "Pagina 12"

        schema = self._extract_news_schema(response)
        if schema:
            title = self._clean_text(schema.get("headline"))
            publish_time = self._parse_datetime(schema.get("datePublished"))
            authors = schema.get("author") or []
            if isinstance(authors, list) and authors:
                names = [self._clean_text(a.get("name")) for a in authors if isinstance(a, dict) and a.get("name")]
                if names:
                    author = ", ".join(names)

        if not title:
            title = self._clean_text(response.css("h1::text").get())
        if not title:
            return

        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content_from_embedded_json(response.text)
        if not content:
            soup = BeautifulSoup(response.text, "html.parser")
            content = self._clean_text((soup.select_one("main") or soup.body).get_text(" ", strip=True) if (soup.select_one("main") or soup.body) else "")
        if not content:
            content = description
        if not content:
            return

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = author
        item["language"] = "es"
        item["section"] = "economia"
        item["scrape_time"] = datetime.now()
        yield item

    def _extract_news_schema(self, response):
        for raw in response.css('script[type="application/ld+json"]::text').getall():
            raw = raw.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            if isinstance(parsed, dict) and parsed.get("@type") == "NewsArticle":
                return parsed
        return None

    def _extract_content_from_embedded_json(self, html):
        # Pagina 12 的正文常嵌在前端数据里，这里直接从嵌入 JSON 提正文。
        matches = re.findall(r'"content":"(.*?)","type":"text"', html)
        parts = []
        for raw in matches:
            try:
                text = json.loads(f'"{raw}"')
            except Exception:
                text = raw
            text = re.sub(r"<[^>]+>", " ", text)
            text = self._clean_text(text)
            if text and len(text) > 30 and text not in parts:
                parts.append(text)
        return "\n\n".join(parts)

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
