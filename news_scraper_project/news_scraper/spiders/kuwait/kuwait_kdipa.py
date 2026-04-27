# 科威特直接投资促进局爬虫，抓取投资促进和合作项目新闻。
import re

import scrapy

from news_scraper.spiders.kuwait.base import KuwaitBaseSpider


class KuwaitKdipaSpider(KuwaitBaseSpider):
    name = "kuwait_kdipa"

    country_code = 'KWT'

    allowed_domains = []
    start_urls = ["https://kdipa.gov.kw/media-center/news/"]

    def parse(self, response):
        emitted = 0
        for href in response.css("a[href*='kdipa.gov.kw/']::attr(href)").getall():
            url = response.urljoin(href)
            if "/media-center/news/" in url:
                continue
            if any(
                blocked in url
                for blocked in [
                    "/about-kdipa/",
                    "/law-and-decisions/",
                    "/media-center/videos/",
                    "/media-center/gallery/",
                    "icrp.kdipa.gov.kw",
                ]
            ):
                continue
            if "kdipa.gov.kw/" not in url:
                continue
            if not self.should_process(url):
                continue
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
        if not title or title.lower() in {"board of directors", "director general message"}:
            return

        page_text = self._clean_text(" ".join(response.css("article *::text").getall()))
        match = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}", page_text)
        publish_time = self._parse_datetime(match.group(0), languages=["en"]) if match else None
        if not self.should_process(response.url, publish_time):
            return

        content = self._extract_content(response, ["article", "main"])
        if not content or "member of the board of directors" in content.lower():
            return

        yield self._build_item(response, title, content, publish_time, "KDIPA", "en", "investment")
