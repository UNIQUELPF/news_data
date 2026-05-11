# 阿根廷pagina12爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

# 阿根廷经济类来源
# 站点：Pagina12
# 入库表：arg_pagina12
# 语言：西班牙语


class ArgentinaPagina12Spider(SmartSpider):
    """阿根廷 Pagina 12 爬虫。

    抓取站点：https://www.pagina12.com.ar
    抓取栏目：economia
    入库表：arg_pagina12
    语言：西班牙语
    """

    name = "argentina_pagina12"


    country_code = "ARG"


    country = "阿根廷"
    language = "en"
    source_timezone = "America/Argentina/Buenos_Aires"
    start_date = "2026-01-01"
    allowed_domains = ["pagina12.com.ar"]
    # 当前 spider 对应的数据库表名。

    # 从经济栏目入口页开始抓取。
    start_urls = [
        "https://www.pagina12.com.ar/economia/",
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
        # Pagina 12 的经济页里会混出其他文章，这里先抓年份型详情链接。
        article_links = response.css('a[href^="/2026/"]::attr(href), a[href^="/2025/"]::attr(href)').getall()

        for href in article_links:
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
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
        item["author"] = "Pagina 12"
        item["section"] = "economia"
        item["language"] = "es"

        if len(item.get("content_plain", "")) > 100:
            yield item

