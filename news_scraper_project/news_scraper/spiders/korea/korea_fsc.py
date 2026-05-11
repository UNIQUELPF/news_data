# 韩国金融委员会爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy

from news_scraper.spiders.korea.base import KoreaBaseSpider


class KoreaFscSpider(KoreaBaseSpider):
    name = "korea_fsc"

    country_code = 'KOR'

    country = '韩国'
    allowed_domains = ["www.fsc.go.kr", "fsc.go.kr"]
    fallback_content_selector = ".detail_cont, .view_cont, .board_view, #contents, article, main"
    start_urls = [
        "https://www.fsc.go.kr/eng/pr010101?curPage=1&srchBeginDt=&srchCtgry=5&srchEndDt=&srchKey=&srchText="
    ]

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return
        has_valid_item_in_window = False
        for href in response.css("a[href*='/eng/pr010101/']::attr(href)").getall():
            if href.startswith("javascript:") or href == "#none":
                continue
            url = response.urljoin(href.split("#")[0])
            if "/eng/pr010101/" not in url or url == self.start_urls[0]:
                continue
            # Only follow detail pages (have numeric ID after /eng/pr010101/)
            if not any(c.isdigit() for c in url.split("/eng/pr010101/")[-1].split("?")[0]):
                continue
            if not self.should_process(url):
                continue
            has_valid_item_in_window = True
            yield scrapy.Request(url, callback=self.parse_detail, dont_filter=self.full_scan)

        # Follow next page of listing
        if has_valid_item_in_window and not self._stop_pagination:
            next_href = response.css("a[href*='curPage=']:not([href*='curPage=1'])::attr(href)").get()
            if next_href and not next_href.startswith("javascript"):
                yield scrapy.Request(
                    response.urljoin(next_href),
                    callback=self.parse_listing,
                    dont_filter=True,
                )

    def parse_detail(self, response):
        title = self._clean_text(
            response.css("meta[property='og:title']::attr(content)").get()
            or response.css("h3::text").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            self.logger.warning(f"No title for {response.url}, body_len={len(response.text)}")
            return

        publish_time = self._parse_datetime(
            response.css("meta[property='article:published_time']::attr(content)").get()
            or response.xpath("//*[contains(@class, 'info')]//*[contains(text(), 'Date')]/following-sibling::*[1]/text()").get()
            or response.xpath("//*[contains(text(), 'Date')]/following::*[1]/text()").get(),
            languages=["en"],
        )
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
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
            self.logger.warning(f"No content extracted for {response.url}, will try ContentEngine fallback")

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Financial Services Commission",
            language="en",
            section="finance",
        )

