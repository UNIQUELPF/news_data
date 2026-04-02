# 柬埔寨税务总局爬虫，抓取英文税务新闻和公告。
import re

import scrapy

from news_scraper.spiders.cambodia.base import CambodiaBaseSpider


class CambodiaTaxSpider(CambodiaBaseSpider):
    name = "cambodia_tax"
    allowed_domains = []
    target_table = "khm_tax"
    start_urls = ["https://www.tax.gov.kh/en"]

    def parse(self, response):
        emitted = 0
        for href in response.css("a[href*='/en/article?key=']::attr(href)").getall():
            url = response.urljoin(href)
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            yield scrapy.Request(url, callback=self.parse_detail)
            emitted += 1
            if emitted >= 12:
                return

    def parse_detail(self, response):
        page_text = self._clean_text(" ".join(response.css(".article-container *::text").getall()))
        title = self._clean_text(
            response.css(".title-header::text").get()
            or response.css("title::text").get()
        )
        match = re.search(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4}", page_text)
        publish_time = self._parse_datetime(match.group(0), languages=["en"]) if match else None
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return
        content = self._extract_content(response, [".article-container", ".content"])
        if not content:
            return
        yield self._build_item(response, title, content, publish_time, "General Department of Taxation", "en", "tax")
