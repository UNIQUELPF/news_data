# 荷兰金融市场管理局爬虫，抓取监管新闻与公告。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.netherlands.base import NetherlandsBaseSpider


class NetherlandsAfmSpider(NetherlandsBaseSpider):
    name = "netherlands_afm"

    country_code = 'NLD'

    country = '荷兰'
    allowed_domains = ["afm.nl", "www.afm.nl"]
    start_urls = ["https://www.afm.nl/en/sector/actueel"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href]"):
            href = (link.get("href") or "").strip()
            if "/en/sector/actueel/" not in href:
                continue
            if href.rstrip("/") == "/en/sector/actueel":
                continue
            full_url = response.urljoin(href.split("?")[0])
            if not self.should_process(full_url):
                continue
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
            or self._clean_text(" ".join(response.css("body ::text").getall()[:120])),
            languages=["en", "nl"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, ["main", "article", ".article", ".content"])
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="AFM",
            language="en",
            section="finance",
        )
