# 巴林国家通用基类，负责建表、增量时间和公共抓取方法。

import io
from datetime import datetime

import dateparser
import scrapy
from pypdf import PdfReader

from news_scraper.items import NewsItem
from news_scraper.utils import get_incremental_state


class BahrainBaseSpider(scrapy.Spider):
    target_table = ""
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
        if not self.target_table:
            return self.default_cutoff

        try:
            state = get_incremental_state(
                self.settings,
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=self.default_cutoff,
                full_scan=self.full_scan,
            )
            self.seen_urls = state["scraped_urls"]
            self.logger.info(
                f"Incremental state loaded via {state['source']} for {self.name}: {len(self.seen_urls)} URLs"
            )
            return state["cutoff_date"]
        except Exception as exc:
            self.logger.error(f"DB init failed for {self.target_table}: {exc}")
            return self.default_cutoff

    def _build_item(self, response, title, content, publish_time, author, language, section):
        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = author
        item["language"] = language
        item["section"] = section
        item["scrape_time"] = datetime.now()
        return item

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
            self.logger.warning(f"PDF parse failed for {self.name}: {exc}")
            return ""

        parts = []
        total_pages = min(len(reader.pages), max_pages)
        for page in reader.pages[:total_pages]:
            try:
                text = self._clean_text(page.extract_text() or "")
            except Exception:
                text = ""
            if text:
                parts.append(text)
        return "\n\n".join(parts)
