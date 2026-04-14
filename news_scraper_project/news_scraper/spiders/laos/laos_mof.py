# 老挝财政部爬虫，抓取财政部新闻和公告。
import re

import scrapy

from news_scraper.spiders.laos.base import LaosBaseSpider


class LaosMofSpider(LaosBaseSpider):
    name = "laos_mof"

    country_code = 'LAO'

    country = '老挝'
    allowed_domains = ["mof.gov.la", "www.mof.gov.la", "soe.mof.gov.la"]
    target_table = "lao_mof"
    start_urls = [
        "https://www.mof.gov.la/",
        "https://soe.mof.gov.la/news",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        emitted = 0
        for href in response.css("a[href*='news_detail/']::attr(href), a[href*='/news/']::attr(href)").getall():
            url = response.urljoin(href)
            if url in self.seen_urls:
                continue
            if "/news" not in url:
                continue
            self.seen_urls.add(url)
            yield scrapy.Request(url, callback=self.parse_detail)
            emitted += 1
            if emitted >= 15:
                return

    def parse_detail(self, response):
        title = self._clean_text(
            response.css("h1::text").get()
            or response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        page_text = self._clean_text(" ".join(response.css("body *::text").getall()))
        match = re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b|\b\d{4}-\d{2}-\d{2}\b", page_text)
        publish_time = self._parse_datetime(match.group(0), languages=["en"]) if match else None
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, ["article", "main", ".content", ".entry-content", ".news-detail"])
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Ministry of Finance Laos",
            language="en",
            section="finance",
        )
