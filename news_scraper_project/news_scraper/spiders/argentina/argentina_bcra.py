from datetime import datetime

import dateparser
import psycopg2
import scrapy
from bs4 import BeautifulSoup

from news_scraper.items import NewsItem


# 阿根廷政府/监管类来源
# 站点：BCRA
# 入库表：arg_bcra
# 语言：西班牙语


class ArgentinaBcraSpider(scrapy.Spider):
    """阿根廷中央银行 BCRA 爬虫。

    抓取站点：https://www.bcra.gob.ar
    抓取栏目：noticias / noticia
    入库表：arg_bcra
    语言：西班牙语
    """

    name = "argentina_bcra"
    allowed_domains = ["bcra.gob.ar"]
    target_table = "arg_bcra"

    start_urls = [
        "https://www.bcra.gob.ar/noticias/",
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
        article_links = response.css('a[href*="/noticia/"]::attr(href), a[href*="/noticias/"]::attr(href)').getall()

        for href in article_links:
            full_url = response.urljoin(href)
            if full_url.rstrip("/") == "https://www.bcra.gob.ar/noticias":
                continue
            if ("/noticia/" not in full_url and "/noticias/" not in full_url) or full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail)

        next_page = response.css("a.next::attr(href), a[rel='next']::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse_listing)

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.css("time::attr(datetime), time::text").get()
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title.replace(" | BCRA", "").strip()
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = "BCRA"
        item["language"] = "es"
        item["section"] = "noticias"
        item["scrape_time"] = datetime.now()
        yield item

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = (
            soup.select_one(".entry-content")
            or soup.select_one(".post-content")
            or soup.select_one(".inside-article")
            or soup.select_one(".site-main")
        )
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, figure, .sharedaddy"):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 12:
                continue
            if text.startswith("miércoles,") or text.startswith("jueves,") or text.startswith("martes,"):
                continue
            if "Banco Central de la República Argentina" in text:
                continue
            if text not in parts:
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
