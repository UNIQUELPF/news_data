# 巴基斯坦sbp爬虫，负责抓取对应站点、机构或栏目内容。

import re

import scrapy

from news_scraper.spiders.pakistan.base import PakistanBaseSpider


class PakistanSbpSpider(PakistanBaseSpider):
    name = "pakistan_sbp"
    allowed_domains = ["sbp.org.pk", "www.sbp.org.pk"]
    target_table = "pak_sbp"
    start_urls = [
        "https://www.sbp.org.pk/press/releases.asp",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        min_year = self.cutoff_date.year if not self.full_scan else None
        for href in response.css("a::attr(href)").getall():
            full_url = response.urljoin(href)
            match = re.search(r"/press/(20\d{2})/index\d*\.asp$", full_url, re.IGNORECASE)
            if not match:
                continue
            year = int(match.group(1))
            if min_year and year < min_year:
                continue
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_year_page)

    def parse_year_page(self, response):
        for link in response.css("a[href$='.pdf']"):
            href = link.attrib.get("href")
            if not href:
                continue

            full_url = response.urljoin(href)
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)

            title = self._clean_text(link.xpath("normalize-space()").get())
            if not title or title.lower() == "click here":
                continue

            publish_time = self._parse_datetime(title, languages=["en"])
            if not publish_time:
                publish_time = self._parse_datetime(full_url, languages=["en"])
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue
            yield scrapy.Request(
                full_url,
                callback=self.parse_pdf,
                cb_kwargs={"title": title, "publish_time": publish_time},
            )

    def parse_pdf(self, response, title, publish_time):
        content = self._extract_pdf_text(response.body)
        if not content:
            content = title

        yield {
            "title": title,
            "content": content,
            "publish_time": publish_time,
            "url": response.url,
            "source_country": "Pakistan",
            "source_name": "State Bank of Pakistan",
            "language": "en",
            "author": "State Bank of Pakistan",
            "section": "press",
        }
