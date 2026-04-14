# 柬埔寨国家通讯社爬虫，抓取 AKP 的经济和政府相关新闻。
import re

import scrapy

from news_scraper.spiders.cambodia.base import CambodiaBaseSpider


class CambodiaAkpSpider(CambodiaBaseSpider):
    name = "cambodia_akp"

    country_code = 'KHM'

    country = '柬埔寨'
    allowed_domains = []
    target_table = "khm_akp"
    start_urls = ["https://www.akp.gov.kh/"]

    def parse(self, response):
        emitted = 0
        for href in response.css("a[href*='/post/detail/']::attr(href)").getall():
            url = response.urljoin(href)
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            yield scrapy.Request(url, callback=self.parse_detail)
            emitted += 1
            if emitted >= 12:
                return

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.xpath("//meta[@name='description']/@content").get()
        )
        if not title:
            return
        text = self._clean_text(" ".join(response.css(".youtube-video *::text").getall()))
        match = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2},\s+\d{4}", text)
        publish_time = self._parse_datetime(match.group(0), languages=["en"]) if match else None
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return
        content = self._extract_content(response, [".youtube-video", "body"])
        if not content:
            return
        yield self._build_item(response, title, content, publish_time, "AKP", "en", "government-news")
