# 卡塔尔国家通讯社爬虫，抓取英文经济和政府新闻。
import re

import scrapy

from news_scraper.spiders.qatar.base import QatarBaseSpider


class QatarQnaSpider(QatarBaseSpider):
    name = "qatar_qna"
    allowed_domains = []
    target_table = "qat_qna"
    start_urls = ["https://qna.org.qa/en/economy"]

    def parse(self, response):
        emitted = 0
        for href in response.css("a[href*='/en/news/news-details']::attr(href), a[href*='/en/News-Area/News/']::attr(href)").getall():
            url = response.urljoin(href)
            if "/en/news/news-details" not in url and "/en/News-Area/News/" not in url:
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
            response.css(".news-details h1::text").get()
            or response.css("h1::text").get()
            or response.xpath("//meta[@property='og:title']/@content").get()
        )
        if not title:
            return

        page_text = self._clean_text(" ".join(response.css(".news-details *::text").getall()))
        match = re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", page_text)
        publish_time = self._parse_datetime(match.group(0), languages=["en"]) if match else None
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, [".news-details", "main"])
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Qatar News Agency",
            language="en",
            section="economy",
        )
