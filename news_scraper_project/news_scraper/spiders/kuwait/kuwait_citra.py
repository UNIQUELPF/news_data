# 科威特通信与信息技术监管局爬虫，抓取英文监管新闻。

import scrapy

from news_scraper.spiders.kuwait.base import KuwaitBaseSpider


class KuwaitCitraSpider(KuwaitBaseSpider):
    name = "kuwait_citra"

    country_code = 'KWT'
    dateparser_settings = {"DATE_ORDER": "DMY"}

    allowed_domains = []
    start_urls = ["https://www.citra.gov.kw/sites/en/Pages/NewsEvents.aspx"]
    fallback_content_selector = '.news-details'

    def parse(self, response):
        emitted = 0
        for href in response.css("a[href*='NewsDetails.aspx?NewsID=']::attr(href)").getall():
            url = response.urljoin(href)
            if not self.should_process(url):
                continue
            yield scrapy.Request(url, callback=self.parse_detail, dont_filter=self.full_scan)
            emitted += 1
            if emitted >= 12:
                return

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h2[1]/text()",
            publish_time_xpath="//p[@class='news-date']/text()",
        )

        if not self.should_process(response.url, item.get('publish_time')):
            return

        item['author'] = 'CITRA'
        item['section'] = 'regulator'

        yield item
