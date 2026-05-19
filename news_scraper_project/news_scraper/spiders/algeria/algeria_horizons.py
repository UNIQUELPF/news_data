# 阿尔及利亚horizons爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

# 阿尔及利亚经济类来源
# 站点：Horizons
# 入库表：dza_horizons
# 语言：法语


class AlgeriaHorizonsSpider(SmartSpider):
    """阿尔及利亚 Horizons 爬虫。

    抓取站点：https://www.horizons.dz
    抓取栏目：Economie
    入库表：dza_horizons
    语言：法语
    """

    name = "algeria_horizons"


    country_code = "DZA"


    country = "阿尔及利亚"
    language = "en"
    source_timezone = "Africa/Algiers"
    allowed_domains = ["horizons.dz"]
    # 当前 spider 对应的数据库表名。

    fallback_content_selector = ".entry-content, .post-content, article"

    # 从经济栏目入口页开始抓取。
    start_urls = [
        "https://www.horizons.dz/category/economie/",
    ]

    # 首次抓取的默认时间边界；后续优先按数据库里最新时间做增量。

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        # Horizons 是典型 WordPress 栏目页，先抓文章链接，再跟进分页。
        article_links = response.css("h2.entry-title a::attr(href), a.more-link::attr(href)").getall()

        has_valid_item_in_window = False
        unique_links = []
        for href in article_links:
            full_url = response.urljoin(href)
            if "/category/" in full_url or not self.should_process(full_url):
                continue
            has_valid_item_in_window = True
            unique_links.append(full_url)

        for article_url in unique_links:
            yield scrapy.Request(article_url, callback=self.parse_detail)

        if self._stop_pagination:
            return

        if has_valid_item_in_window:
            next_page = response.css("a.next.page-numbers::attr(href), link[rel='next']::attr(href)").get()
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
        item["author"] = "Horizons"
        item["section"] = "economie"
        item["language"] = "fr"

        if len(item.get("content_plain", "")) > 100:
            yield item

