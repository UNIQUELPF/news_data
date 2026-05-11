# 阿尔及利亚dzair tube爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

# 阿尔及利亚经济类来源
# 站点：Dzair Tube
# 入库表：dza_dzair_tube
# 语言：阿拉伯语


class AlgeriaDzairTubeSpider(SmartSpider):
    """阿尔及利亚 Dzair Tube 爬虫。

    抓取站点：https://www.dzair-tube.dz
    抓取栏目：economie
    入库表：dza_dzair_tube
    语言：阿拉伯语
    """

    name = "algeria_dzair_tube"


    country_code = "DZA"


    country = "阿尔及利亚"
    language = "en"
    source_timezone = "Africa/Algiers"
    start_date = "2026-01-01"
    allowed_domains = ["dzair-tube.dz"]
    # 当前 spider 对应的数据库表名。

    fallback_content_selector = ".entry-content, article"

    # 从经济栏目入口页开始抓取。
    start_urls = [
        "https://www.dzair-tube.dz/economie/",
    ]

    # 首次抓取的默认时间边界；后续优先按数据库里最新时间做增量。

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, meta={"page": 1}, dont_filter=True)

    def parse_listing(self, response):
        # Dzair Tube 的经济栏目是 WordPress 结构，列表页取文章链接并继续翻页。
        article_links = response.css("h2 a::attr(href)").getall()

        has_valid_item_in_window = False
        unique_links = []
        for href in article_links:
            full_url = response.urljoin(href)
            if "/economie/page/" in full_url or not self.should_process(full_url):
                continue
            has_valid_item_in_window = True
            unique_links.append(full_url)

        for article_url in unique_links:
            yield scrapy.Request(article_url, callback=self.parse_detail, dont_filter=self.full_scan)

        if self._stop_pagination:
            return

        if has_valid_item_in_window:
            next_page = response.css("a.next.page-numbers::attr(href), link[rel='next']::attr(href)").get()
            if next_page:
                next_page_num = response.meta.get("page", 1) + 1
                yield response.follow(next_page, callback=self.parse_listing, meta={"page": next_page_num})

    def parse_detail(self, response):
        item = self.auto_parse_item(response)
        if not item.get("title") or not item.get("content_plain"):
            return

        publish_time = item.get("publish_time")
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        # Spider-specific overrides
        author = response.xpath("//*[contains(text(), 'بقلم:')]/text()").get()
        if author and "بقلم:" in author:
            author = author.split("بقلم:", 1)[1].strip()
        item["author"] = author or "Dzair Tube"
        item["section"] = "economie"
        item["language"] = "ar"

        if len(item.get("content_plain", "")) > 100:
            yield item

