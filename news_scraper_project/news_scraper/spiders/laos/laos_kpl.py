# 老挝通讯社爬虫，抓取英文经济与政府新闻。
import re

import scrapy

from news_scraper.spiders.laos.base import LaosBaseSpider


class LaosKplSpider(LaosBaseSpider):
    name = "laos_kpl"

    country_code = 'LAO'

    allowed_domains = ["kpl.gov.la", "www.kpl.gov.la"]
    start_urls = [
        "https://kpl.gov.la/En/News.aspx?cat=10",
        "https://kpl.gov.la/En/News.aspx?cat=9",
    ]

    dateparser_settings = {"DATE_ORDER": "DMY"}

    def parse(self, response):
        emitted = 0
        for li in response.css('ul.news-story li'):
            href = li.css('a[href*="detail.aspx"]::attr(href)').get()
            if not href:
                continue
            url = response.urljoin(href)
            if "/En/" not in url:
                continue
            date_str = li.css('p.uk-text-small.uk-text-muted::text').get()
            publish_time = self.parse_date(date_str) if date_str else None
            if not self.should_process(url, publish_time):
                continue
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
        publish_time = self.parse_date(match.group(0)) if match else None
        if not self.should_process(response.url, publish_time):
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
