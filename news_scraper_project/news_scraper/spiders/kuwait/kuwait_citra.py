# 科威特通信与信息技术监管局爬虫，抓取英文监管新闻。
import re

import scrapy

from news_scraper.spiders.kuwait.base import KuwaitBaseSpider


class KuwaitCitraSpider(KuwaitBaseSpider):
    name = "kuwait_citra"

    country_code = 'KWT'

    country = '科威特'
    allowed_domains = []
    target_table = "kwt_citra"
    start_urls = ["https://www.citra.gov.kw/sites/en/Pages/NewsEvents.aspx"]

    def parse(self, response):
        emitted = 0
        for href in response.css("a[href*='NewsDetails.aspx?NewsID=']::attr(href)").getall():
            url = response.urljoin(href)
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            yield scrapy.Request(url, callback=self.parse_detail)
            emitted += 1
            if emitted >= 12:
                return

    def parse_detail(self, response):
        content = self._extract_content(response, [".news-details", "main", ".content"])
        if not content:
            return

        title = self._clean_text(
            response.css("title::text").get()
            or response.xpath("//meta[@property='og:title']/@content").get()
        )
        if not title:
            title = content.split(". ", 1)[0][:180]

        page_text = self._clean_text(" ".join(response.css(".news-details *::text").getall()))
        match = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}", page_text)
        publish_time = self._parse_datetime(match.group(0), languages=["en"]) if match else None
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        yield self._build_item(response, title, content, publish_time, "CITRA", "en", "regulator")
