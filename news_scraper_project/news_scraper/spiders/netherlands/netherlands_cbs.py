# 荷兰统计局爬虫，抓取英文统计新闻与数据发布。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.netherlands.base import NetherlandsBaseSpider


class NetherlandsCbsSpider(NetherlandsBaseSpider):
    name = "netherlands_cbs"
    allowed_domains = []
    target_table = "nld_cbs"
    start_urls = ["data:,netherlands_cbs_start"]
    feed_url = "https://www.cbs.nl/en-gb/rss-feeds/economie"

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        xml_text = self._fetch_html(self.feed_url)
        soup = BeautifulSoup(xml_text, "xml")
        for node in soup.find_all("item"):
            full_url = self._clean_text((node.link.text if node.link else "")).split("?")[0]
            if "/en-gb/news/" not in full_url:
                continue
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            try:
                detail_html = self._fetch_html(full_url)
            except Exception:
                continue
            item = next(self.parse_detail(self._make_response(full_url, detail_html)), None)
            if item:
                yield item

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or self._clean_text(" ".join(response.css("body ::text").getall()[:100])),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, ["main", "article", ".content", ".article"])
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Statistics Netherlands",
            language="en",
            section="statistics",
        )
