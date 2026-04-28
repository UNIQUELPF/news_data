# 韩国金融委员会爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy

from news_scraper.spiders.korea.base import KoreaBaseSpider


class KoreaFscSpider(KoreaBaseSpider):
    name = "korea_fsc"

    country_code = 'KOR'

    country = '韩国'
    allowed_domains = ["www.fsc.go.kr", "fsc.go.kr"]
    start_urls = [
        "https://www.fsc.go.kr/eng/pr010101?curPage=1&srchBeginDt=&srchCtgry=5&srchEndDt=&srchKey=&srchText="
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        for href in response.css("a[href*='/eng/pr010101/']::attr(href)").getall():
            if href.startswith("javascript:"):
                continue
            url = response.urljoin(href.split("#")[0])
            if "/eng/pr010101/" not in url or url == self.start_urls[0]:
                continue
            if not self.should_process(url):
                continue
            yield scrapy.Request(url, callback=self.parse_detail)

    def parse_detail(self, response):
        title = self._clean_text(
            response.css("meta[property='og:title']::attr(content)").get()
            or response.css("h3::text").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.css("meta[property='article:published_time']::attr(content)").get()
            or response.xpath("//*[contains(@class, 'info')]//*[contains(text(), 'Date')]/following-sibling::*[1]/text()").get()
            or response.xpath("//*[contains(text(), 'Date')]/following::*[1]/text()").get(),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_blocks(
            response,
            [
                ".detail_cont p",
                ".view_cont p",
                ".board_view p",
                "#contents p",
                "article p",
                "main p",
            ],
        )
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Financial Services Commission",
            language="en",
            section="finance",
        )

