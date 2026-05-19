# 阿尔及利亚elkhabar爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

# 阿尔及利亚经济类来源
# 站点：El Khabar
# 入库表：dza_elkhabar
# 语言：阿拉伯语


class AlgeriaElkhabarSpider(SmartSpider):
    """阿尔及利亚 El Khabar 爬虫。

    抓取站点：https://www.elkhabar.com
    抓取栏目：economie
    入库表：dza_elkhabar
    语言：阿拉伯语
    """

    name = "algeria_elkhabar"


    country_code = "DZA"


    country = "阿尔及利亚"
    language = "en"
    source_timezone = "Africa/Algiers"
    allowed_domains = ["elkhabar.com"]
    # 当前 spider 对应的数据库表名。

    fallback_content_selector = "article"

    # 从经济栏目入口页开始翻页抓取。
    start_urls = [
        "https://www.elkhabar.com/economie",
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
        # El Khabar 栏目页通过 ?page=N 分页，列表里只保留经济文章详情链接。
        article_links = response.css('a[href*="/economie/"]::attr(href)').getall()

        has_valid_item_in_window = False
        unique_links = []
        for href in article_links:
            full_url = response.urljoin(href)
            if full_url.rstrip("/") == "https://www.elkhabar.com/economie":
                continue
            if "?page=" in full_url or not self.should_process(full_url):
                continue
            has_valid_item_in_window = True
            unique_links.append(full_url)

        for article_url in unique_links:
            yield scrapy.Request(article_url, callback=self.parse_detail)

        if self._stop_pagination:
            return

        if has_valid_item_in_window:
            current_page = response.meta.get("page", 1)
            next_page = current_page + 1
            next_url = f"https://www.elkhabar.com/economie?page={next_page}"
            if response.css(f'a[href="/economie?page={next_page}"]'):
                yield scrapy.Request(next_url, callback=self.parse_listing, meta={"page": next_page})

    def parse_detail(self, response):
        item = self.auto_parse_item(response)
        if not item.get("title") or not item.get("content_plain"):
            return

        publish_time = item.get("publish_time")
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        # Spider-specific overrides
        author = response.css('a[href*="/profile/"]::text').get()
        item["author"] = author.strip() if author else "El Khabar"
        item["section"] = "economie"
        item["language"] = "ar"

        if len(item.get("content_plain", "")) > 100:
            yield item

