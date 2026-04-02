# 东帝汶国家通用基类，负责建表、增量时间和公共抓取方法。

import io
from datetime import datetime

import dateparser
import psycopg2
import requests
import scrapy
from pypdf import PdfReader
from scrapy.http import HtmlResponse

from news_scraper.items import NewsItem


class TimorLesteBaseSpider(scrapy.Spider):
    target_table = ""
    default_cutoff = datetime(2025, 1, 1)
    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    request_timeout = 30
    verify_ssl = True

    def __init__(self, full_scan="false", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_scan = str(full_scan).lower() in ("1", "true", "yes")
        self.cutoff_date = self.default_cutoff
        self.seen_urls = set()
        self.request_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

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

    def _fetch(self, url, method="GET", json_data=None, headers=None):
        request_headers = dict(self.request_headers)
        if headers:
            request_headers.update(headers)
        response = requests.request(
            method=method,
            url=url,
            headers=request_headers,
            json=json_data,
            timeout=self.request_timeout,
            allow_redirects=True,
            verify=self.verify_ssl,
        )
        response.raise_for_status()
        return response

    def _fetch_html(self, url, method="GET", json_data=None, headers=None):
        return self._fetch(url, method=method, json_data=json_data, headers=headers).text

    def _fetch_json(self, url, method="GET", json_data=None, headers=None):
        return self._fetch(url, method=method, json_data=json_data, headers=headers).json()

    def _make_response(self, url, html):
        return HtmlResponse(url=url, body=html.encode("utf-8"), encoding="utf-8")

    def _extract_pdf_text(self, pdf_bytes, max_pages=4):
        if not pdf_bytes:
            return ""
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
        except Exception as exc:
            self.logger.warning(f"PDF parse failed for {self.name}: {exc}")
            return ""

        parts = []
        for page in reader.pages[: min(len(reader.pages), max_pages)]:
            try:
                text = self._clean_text(page.extract_text() or "")
            except Exception:
                text = ""
            if text:
                parts.append(text)
        return "\n\n".join(parts)
