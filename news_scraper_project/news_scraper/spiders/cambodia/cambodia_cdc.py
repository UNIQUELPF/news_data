# 柬埔寨发展理事会爬虫，抓取 CDC 投资和项目动态新闻。
import scrapy

from news_scraper.spiders.cambodia.base import CambodiaBaseSpider


class CambodiaCdcSpider(CambodiaBaseSpider):
    name = "cambodia_cdc"

    country_code = 'KHM'

    country = '柬埔寨'
    allowed_domains = []
    target_table = "khm_cdc"
    start_urls = ["https://cdc.gov.kh/cdc-news/"]

    def parse(self, response):
        emitted = 0
        for href in response.css("a[href*='/recent-news/']::attr(href)").getall():
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
            response.css("h1::text").get()
            or response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("title::text").get()
        )
        if not title:
            return
        content = self._extract_content(response, [".page-content-section", "body"])
        if not content:
            return
        yield self._build_item(response, title, content, None, "CDC Cambodia", "km", "investment")
