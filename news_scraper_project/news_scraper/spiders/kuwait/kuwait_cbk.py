# 科威特中央银行爬虫，抓取英文公告和新闻稿。
import re
from datetime import datetime

import scrapy

from news_scraper.spiders.kuwait.base import KuwaitBaseSpider


class KuwaitCbkSpider(KuwaitBaseSpider):
    name = "kuwait_cbk"
    allowed_domains = []
    target_table = "kwt_cbk"
    start_urls = ["https://www.cbk.gov.kw/en/"]

    def parse(self, response):
        emitted = 0
        for href in response.css("a[href*='/en/cbk-news/announcements-and-press-releases/']::attr(href)").getall():
            url = response.urljoin(href)
            if url.endswith("/press-releases") or url.endswith("/announcements"):
                continue
            if "/202" not in url:
                continue
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            yield scrapy.Request(url, callback=self.parse_detail)
            emitted += 1
            if emitted >= 12:
                return

    def parse_detail(self, response):
        title = self._clean_text(
            response.css("article h2::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        lowered_title = title.lower()
        if "page not found" in lowered_title or "internal server error" in lowered_title:
            return

        page_text = self._clean_text(" ".join(response.css("article *::text").getall()))
        if "an error has occured while retrieving the page you requested" in page_text.lower():
            return

        publish_time = None
        match = re.search(r"\b\d{2}\.\d{2}\.\d{2}\b", page_text)
        if match:
            try:
                publish_time = datetime.strptime(match.group(0), "%d.%m.%y")
            except ValueError:
                publish_time = None

        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, ["article", ".page-content", "main"])
        if not content:
            return

        yield self._build_item(response, title, content, publish_time, "Central Bank of Kuwait", "en", "central-bank")
