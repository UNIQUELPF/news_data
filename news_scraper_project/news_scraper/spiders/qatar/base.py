# 卡塔尔国家通用基类，负责建表、增量时间和公共抓取方法。
from datetime import datetime
import json

import dateparser
import requests
import scrapy
import urllib3
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from scrapy.http import HtmlResponse

from news_scraper.items import NewsItem
from news_scraper.utils import get_incremental_state


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class QatarBaseSpider(scrapy.Spider):
    target_table = ""
    default_cutoff = datetime(2025, 1, 1)
    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    request_timeout = 30

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

    def _fetch_html(self, url):
        try:
            response = requests.get(
                url,
                headers=self.request_headers,
                timeout=self.request_timeout,
                allow_redirects=True,
                verify=False,
            )
            response.raise_for_status()
            return response.text
        except Exception:
            response = curl_requests.get(
                url,
                headers=self.request_headers,
                timeout=self.request_timeout,
                allow_redirects=True,
                impersonate="chrome124",
                verify=False,
            )
            response.raise_for_status()
            return response.text

    def _fetch_json(self, url):
        return json.loads(self._fetch_html(url))

    def _make_response(self, url, html):
        return HtmlResponse(url=url, body=html.encode("utf-8"), encoding="utf-8")

    def _extract_content(self, response, selectors):
        soup = BeautifulSoup(response.text, "html.parser")
        for selector in selectors:
            root = soup.select_one(selector)
            if not root:
                continue
            for unwanted in root.select(
                "script, style, nav, footer, header, aside, form, "
                ".share, .breadcrumb, .social-share, .article-tags, .related-articles"
            ):
                unwanted.decompose()
            parts = []
            for node in root.find_all(["p", "li", "h2", "h3", "h4", "div"], recursive=True):
                text = self._clean_text(node.get_text(" ", strip=True))
                if not text or len(text) < 30:
                    continue
                if text not in parts:
                    parts.append(text)
            if parts:
                return "\n\n".join(parts)
        return ""
