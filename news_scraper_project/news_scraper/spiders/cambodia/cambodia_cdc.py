# 柬埔寨发展理事会爬虫，抓取 CDC 投资和项目动态新闻。
import scrapy

from news_scraper.spiders.cambodia.base import CambodiaBaseSpider


class CambodiaCdcSpider(CambodiaBaseSpider):
    name = "cambodia_cdc"

    country_code = 'KHM'

    country = '柬埔寨'
    allowed_domains = []
    start_urls = ["https://cdc.gov.kh/cdc-news/"]

    fallback_content_selector = "article, main"

    def parse(self, response):
        if self._stop_pagination:
            return

        has_valid_item_in_window = False
        for container in response.css('.parent-page'):
            href = container.css('a[href*="/recent-news/"]::attr(href)').get()
            if not href:
                continue
            url = response.urljoin(href)
            date_str = container.css('i.fa-calendar::text').get()
            publish_time = self._parse_datetime(date_str, languages=["en"]) if date_str else None
            if not self.should_process(url, publish_time):
                continue
            has_valid_item_in_window = True
            yield scrapy.Request(url, callback=self.parse_detail)
        if not has_valid_item_in_window:
            self._stop_pagination = True

    def parse_detail(self, response):
        title = self._clean_text(
            response.css("h1::text").get()
            or response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.css("time::attr(datetime)").get(),
            languages=["en"],
        )
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        content = self._extract_content(response, [".page-content-section", "body"])
        if not content:
            return
        yield self._build_item(response, title, content, publish_time, "CDC Cambodia", "km", "investment")
