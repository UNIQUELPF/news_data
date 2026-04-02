# 荷兰企业局爬虫，抓取英文产业、投资与政策支持新闻。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.netherlands.base import NetherlandsBaseSpider


class NetherlandsRvoSpider(NetherlandsBaseSpider):
    name = "netherlands_rvo"
    allowed_domains = ["english.rvo.nl", "rvo.nl", "www.rvo.nl"]
    target_table = "nld_rvo"
    start_urls = ["https://english.rvo.nl/en/news"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href]"):
            href = (link.get("href") or "").strip()
            if "/en/news/" not in href:
                continue
            full_url = response.urljoin(href.split("?")[0])
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

        content = self._extract_content(response, ["main", "article", ".page-content", ".content"])
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="RVO",
            language="en",
            section="economy",
        )
