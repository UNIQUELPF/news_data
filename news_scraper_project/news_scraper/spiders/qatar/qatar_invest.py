# 卡塔尔投资促进局爬虫，抓取招商和投资相关新闻。
import re

import scrapy

from news_scraper.spiders.qatar.base import QatarBaseSpider


class QatarInvestSpider(QatarBaseSpider):
    name = "qatar_invest"

    country_code = 'QAT'

    country = '卡塔尔'
    allowed_domains = []
    target_table = "qat_invest"
    start_urls = ["https://www.invest.qa/en/media-centre/news-and-articles"]

    def parse(self, response):
        emitted = 0
        for href in response.css("a[href*='/en/media-centre/news-and-articles/']::attr(href)").getall():
            url = response.urljoin(href)
            if url.rstrip("/") == self.start_urls[0]:
                continue
            if "/en/media-centre/news-and-articles/" not in url:
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
            response.css("h1::text").get()
            or response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        page_text = self._clean_text(" ".join(response.css("main *::text").getall()))
        match = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}", page_text)
        publish_time = self._parse_datetime(match.group(0), languages=["en"]) if match else None
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(
            response,
            [".news-details", ".section-content", ".entry-content", "main"],
        )
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Invest Qatar",
            language="en",
            section="investment",
        )
