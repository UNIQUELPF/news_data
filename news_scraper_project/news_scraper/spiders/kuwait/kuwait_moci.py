# 科威特工商部爬虫，抓取英文经济简报及其 PDF 正文。
import re
from datetime import datetime

import scrapy

from news_scraper.spiders.kuwait.base import KuwaitBaseSpider


class KuwaitMociSpider(KuwaitBaseSpider):
    name = "kuwait_moci"

    country_code = 'KWT'

    country = '科威特'
    allowed_domains = []
    target_table = "kwt_moci"
    start_urls = ["https://www.moci.gov.kw/en/media/economic-newsletter/"]

    def parse(self, response):
        for href in response.css("a[href*='/en/media/economic-newsletter/economic-']::attr(href)").getall():
            url = response.urljoin(href)
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            yield scrapy.Request(url, callback=self.parse_year)

    def parse_year(self, response):
        year_match = re.search(r"(20\d{2})", response.url)
        year = int(year_match.group(1)) if year_match else None

        for href in response.css("a[href$='.pdf']::attr(href), a[href*='.pdf?']::attr(href)").getall():
            url = response.urljoin(href)
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            yield scrapy.Request(url, callback=self.parse_pdf, cb_kwargs={"year": year})

    def parse_pdf(self, response, year=None):
        title = self._clean_text(response.url.split("/")[-1].split("?")[0])
        content = self._extract_pdf_text(response.body, max_pages=6)
        if not content:
            return

        publish_time = datetime(year, 1, 1) if year else None
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        yield self._build_item(
            response,
            title,
            content,
            publish_time,
            "Ministry of Commerce and Industry",
            "en",
            "economy",
        )
