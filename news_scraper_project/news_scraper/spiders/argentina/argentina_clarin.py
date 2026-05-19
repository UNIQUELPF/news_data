# 阿根廷clarin爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

# 阿根廷经济类来源
# 站点：Clarin
# 入库表：arg_clarin
# 语言：西班牙语


class ArgentinaClarinSpider(SmartSpider):
    """阿根廷 Clarin 爬虫。

    抓取站点：https://www.clarin.com
    抓取栏目：economia
    入库表：arg_clarin
    语言：西班牙语
    """

    name = "argentina_clarin"


    country_code = "ARG"


    country = "阿根廷"
    language = "en"
    source_timezone = "America/Argentina/Buenos_Aires"
    allowed_domains = ["clarin.com"]
    # 当前 spider 对应的数据库表名。

    # Clarín 的经济栏目页能直接拿到文章链接。
    fallback_content_selector = "article, main"

    start_urls = [
        "https://www.clarin.com/economia/",
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
        # 列表页只保留经济频道详情链接。
        article_links = response.css('a[href*="/economia/"]::attr(href)').getall()

        for href in article_links:
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
                continue
            if "/economia/" not in full_url or not full_url.endswith(".html"):
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        item = self.auto_parse_item(response)
        if not item.get("title") or not item.get("content_plain"):
            return

        publish_time = item.get("publish_time")
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        # Spider-specific overrides
        item["author"] = "Clarin"
        item["section"] = "economia"
        item["language"] = "es"

        if len(item.get("content_plain", "")) > 100:
            yield item

