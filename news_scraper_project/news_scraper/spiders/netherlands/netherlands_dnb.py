# 荷兰央行爬虫，抓取英文新闻与金融稳定相关内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.netherlands.base import NetherlandsBaseSpider


class NetherlandsDnbSpider(NetherlandsBaseSpider):
    name = "netherlands_dnb"

    country_code = 'NLD'

    country = '荷兰'
    allowed_domains = []
    start_urls = ["data:,netherlands_dnb_start"]
    feed_url = "https://www.dnb.nl/en/rss/16451/6882"

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        xml_text = self._fetch_html(self.feed_url)
        soup = BeautifulSoup(xml_text, "xml")
        emitted = 0
        for node in soup.find_all("item"):
            full_url = self._clean_text((node.link.text if node.link else "")).split("?")[0]
            if "/en/" not in full_url:
                continue
            if not self.should_process(full_url):
                continue
            try:
                detail_html = self._fetch_html(full_url)
            except Exception:
                continue
            item = next(self.parse_detail(self._make_response(full_url, detail_html)), None)
            if item:
                yield item
                emitted += 1
                if emitted >= 10:
                    break

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
            or self._clean_text(" ".join(response.css("body ::text").getall()[:120])),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, ["main", "article", ".article-content", ".content"])
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="De Nederlandsche Bank",
            language="en",
            section="economy",
        )
