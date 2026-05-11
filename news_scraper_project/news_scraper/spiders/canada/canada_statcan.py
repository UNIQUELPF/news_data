# 加拿大统计局爬虫，抓取 The Daily 统计发布。
import re
from datetime import datetime

import scrapy

from news_scraper.spiders.canada.base import CanadaBaseSpider


class CanadaStatcanSpider(CanadaBaseSpider):
    name = "canada_statcan"

    country_code = 'CAN'

    country = '加拿大'
    allowed_domains = []
    start_urls = ["https://www150.statcan.gc.ca/n1/dai-quo/index-eng.htm"]

    def parse(self, response):
        emitted = 0
        for href in response.css('a[href*="/daily-quotidien/"]::attr(href)').getall():
            url = response.urljoin(href)
            date_match = re.search(r"/daily-quotidien/(\d{2})(\d{2})(\d{2})/", url)
            publish_time = None
            if date_match:
                try:
                    publish_time = datetime.strptime(f"20{date_match.group(1)}{date_match.group(2)}{date_match.group(3)}", "%Y%m%d")
                except ValueError:
                    pass
            if not self.should_process(url, publish_time):
                continue
            yield scrapy.Request(url, callback=self.parse_detail)
            emitted += 1
            if emitted >= 12:
                return

    def parse_detail(self, response):
        title = self._clean_text(
            response.css("h1::text").get()
            or response.xpath("//meta[@name='dcterms.title']/@content").get()
            or response.css("title::text").get()
        )
        if not title:
            return
        publish_time = self._parse_datetime(
            response.xpath("//meta[@name='dcterms.issued']/@content").get()
            or response.xpath("//meta[@name='dcterms.modified']/@content").get()
        )
        if publish_time and publish_time < self.cutoff_date:
            return
        content = self._extract_content(response, ["main"])
        if not content:
            return
        yield self._build_item(response, title, content, publish_time, "Statistics Canada", "en", "statistics")
