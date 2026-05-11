# 荷兰统计局爬虫，抓取英文统计新闻与数据发布。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.netherlands.base import NetherlandsBaseSpider


class NetherlandsCbsSpider(NetherlandsBaseSpider):
    name = "netherlands_cbs"

    country_code = 'NLD'

    country = '荷兰'
    allowed_domains = []
    start_urls = ["data:,netherlands_cbs_start"]
    feed_url = "https://www.cbs.nl/en-gb/rss-feeds/economie"

    fallback_content_selector = "article, main"

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return

        xml_text = self._fetch_html(self.feed_url)
        soup = BeautifulSoup(xml_text, "xml")
        has_valid_item_in_window = False
        for node in soup.find_all("item"):
            full_url = self._clean_text((node.link.text if node.link else "")).split("?")[0]
            if "/en-gb/news/" not in full_url:
                continue
            pubDate_text = node.pubDate.text if node.pubDate else None
            publish_time = self._parse_datetime(pubDate_text, languages=["en"]) if pubDate_text else None
            if not self.should_process(full_url, publish_time):
                continue
            if self._stop_pagination:
                break
            try:
                detail_html = self._fetch_html(full_url)
            except Exception:
                continue
            item = next(self.parse_detail(self._make_response(full_url, detail_html)), None)
            if item:
                has_valid_item_in_window = True
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
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
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
