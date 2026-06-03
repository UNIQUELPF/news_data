# 巴基斯坦国家通用基类，负责建表、增量时间和公共抓取方法。

import io
from datetime import datetime

import dateparser
import psycopg2
import scrapy
from news_scraper.utils import get_incremental_state
from pypdf import PdfReader


class PakistanBaseSpider(scrapy.Spider):
    target_table = ""
    default_cutoff = datetime(2026, 1, 1)
    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
            "https": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
        },
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
        if not settings or not self.target_table:
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

    def _build_item(self, response, title, content, publish_time, author, language, section):
        raw_html = getattr(response, "text", "")
        if raw_html:
            from pipeline.content_engine import ContentEngine
            content_data = ContentEngine.process(
                raw_html=raw_html,
                base_url=response.url,
                fallback_selector=getattr(self, "fallback_content_selector", None),
            ) or {}
        else:
            content_data = {}

        images = content_data.get("images") or []
        if not images:
            images = self._extract_og_image(response)

        content_cleaned = content_data.get("content_cleaned") or content
        content_markdown = content_data.get("content_markdown") or content
        content_plain = content_data.get("content_plain") or content

        return {
            "url": response.url,
            "title": title,
            "raw_html": raw_html,
            "content_plain": content_plain,
            "content_cleaned": content_cleaned,
            "content_markdown": content_markdown,
            "content": content_plain,
            "images": images,
            "publish_time": publish_time,
            "author": author,
            "language": language,
            "section": section,
        }

    def _extract_og_image(self, response):
        if not hasattr(response, "text"):
            return []
        img = response.xpath("//meta[@property='og:image']/@content").get()
        if img:
            return [response.urljoin(img)]
        return []

    def _clean_text(self, value):
        if not value:
            return ""
        return " ".join(str(value).replace("\x00", " ").split()).strip()

    def _parse_datetime(self, value, languages=None):
        if not value:
            return None
        parsed = dateparser.parse(value, languages=languages, settings={"TIMEZONE": "UTC"})
        if not parsed:
            return None
        return parsed.replace(tzinfo=None)

    def _extract_pdf_text(self, pdf_bytes, max_pages=4):
        if not pdf_bytes:
            return ""

        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
        except Exception as exc:
            self.logger.warning(f"PDF parse failed for {getattr(self, 'name', 'spider')}: {exc}")
            return ""

        parts = []
        total_pages = min(len(reader.pages), max_pages)
        for page in reader.pages[:total_pages]:
            try:
                text = self._clean_text(page.extract_text() or "")
            except Exception:
                text = ""
            if not text:
                continue
            parts.append(text)

        if not parts:
            return ""

        return "\n\n".join(parts)
