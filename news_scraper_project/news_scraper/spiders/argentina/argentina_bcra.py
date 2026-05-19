# 阿根廷bcra爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

# 阿根廷政府/监管类来源
# 站点：BCRA
# 入库表：arg_bcra
# 语言：西班牙语


class ArgentinaBcraSpider(SmartSpider):
    """阿根廷中央银行 BCRA 爬虫。

    抓取站点：https://www.bcra.gob.ar
    抓取栏目：noticias / noticia
    入库表：arg_bcra
    语言：西班牙语
    """

    name = "argentina_bcra"
    strict_date_required = False


    country_code = "ARG"


    country = "阿根廷"
    language = "en"
    source_timezone = "America/Argentina/Buenos_Aires"
    allowed_domains = ["bcra.gob.ar"]

    fallback_content_selector = ".et_pb_post_content, .entry-content, .post-content, .inside-article, .site-main"

    start_urls = [
        "https://www.bcra.gob.ar/noticias/",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return

        article_links = response.css('a[href*="/noticia/"]::attr(href), a[href*="/noticias/"]::attr(href)').getall()

        has_valid_item_in_window = False

        for href in article_links:
            full_url = response.urljoin(href)
            if full_url.rstrip("/") == "https://www.bcra.gob.ar/noticias":
                continue
            if ("/noticia/" not in full_url and "/noticias/" not in full_url) or not self.should_process(full_url):
                continue
            has_valid_item_in_window = True
            yield scrapy.Request(full_url, callback=self.parse_detail)

        if has_valid_item_in_window:
            next_page = response.css("a.next::attr(href), a[rel='next']::attr(href)").get()
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
        item["title"] = item["title"].replace(" | BCRA", "").strip()
        item["author"] = "BCRA"
        item["section"] = "noticias"
        item["language"] = "es"

        if len(item.get("content_plain", "")) > 100:
            yield item

