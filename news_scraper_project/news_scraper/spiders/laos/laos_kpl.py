# 老挝通讯社爬虫，抓取英文经济与政府新闻。
import re

import scrapy

from news_scraper.spiders.laos.base import LaosBaseSpider


class LaosKplSpider(LaosBaseSpider):
    name = "laos_kpl"

    country_code = 'LAO'

    country = '老挝'
    allowed_domains = ["kpl.gov.la", "www.kpl.gov.la"]
    target_table = "lao_kpl"
    start_urls = ["https://kpl.gov.la/En/"]

    def parse(self, response):
        emitted = 0
        for href in response.css("a[href*='detail.aspx']::attr(href)").getall():
            url = response.urljoin(href)
            if "/En/" not in url or url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            yield scrapy.Request(url, callback=self.parse_detail)
            emitted += 1
            if emitted >= 15:
                return

    def parse_detail(self, response):
        title = self._clean_text(
            response.css("h1::text").get()
            or response.css("title::text").get()
            or response.xpath("//meta[@property='og:title']/@content").get()
        )
        if not title:
            return

        page_text = self._clean_text(" ".join(response.css("body *::text").getall()))
        match = re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", page_text)
        publish_time = self._parse_datetime(match.group(0), languages=["en"]) if match else None
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, [".content", ".detail", "article", "main", "body"])
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="KPL",
            language="en",
            section="government",
        )
