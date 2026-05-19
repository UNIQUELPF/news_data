# 阿根廷economia gov爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

# 阿根廷政府类来源
# 站点：Argentina Economia
# 入库表：arg_economia_gov
# 语言：西班牙语


class ArgentinaEconomiaGovSpider(SmartSpider):
    """阿根廷经济部官网爬虫。

    抓取站点：https://www.argentina.gob.ar/economia
    抓取栏目：noticias
    入库表：arg_economia_gov
    语言：西班牙语
    """

    name = "argentina_economia_gov"


    country_code = "ARG"


    country = "阿根廷"
    language = "en"
    source_timezone = "America/Argentina/Buenos_Aires"
    strict_date_required = False
    allowed_domains = ["argentina.gob.ar"]

    fallback_content_selector = "article, main"

    start_urls = [
        "https://www.argentina.gob.ar/economia/noticias",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        article_links = response.css('a[href*="/noticias/"]::attr(href)').getall()

        has_valid_item_in_window = False

        for href in article_links:
            full_url = response.urljoin(href)
            if "/noticias/" not in full_url or not self.should_process(full_url):
                continue
            has_valid_item_in_window = True
            yield scrapy.Request(full_url, callback=self.parse_detail)

        if self._stop_pagination:
            return

        if has_valid_item_in_window:
            next_page = response.css("li.pager__item--next a::attr(href), a[rel='next']::attr(href)").get()
            if next_page:
                yield response.follow(next_page, callback=self.parse_listing)

    def parse_detail(self, response):
        item = self.auto_parse_item(response)
        if not item.get("title") or not item.get("content_plain"):
            return

        publish_time = item.get("publish_time")
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        # Spider-specific overrides
        item["author"] = "Ministerio de Economía"
        item["section"] = "noticias"
        item["language"] = "es"

        if len(item.get("content_plain", "")) > 100:
            yield item

