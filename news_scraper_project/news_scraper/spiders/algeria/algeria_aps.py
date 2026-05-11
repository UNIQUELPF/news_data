# 阿尔及利亚aps爬虫，负责抓取对应站点、机构或栏目内容。

import re

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

# 阿尔及利亚经济类来源
# 站点：APS
# 入库表：dza_aps
# 语言：阿拉伯语


class AlgeriaApsSpider(SmartSpider):
    """阿尔及利亚 APS 爬虫。

    抓取站点：https://www.aps.dz
    抓取栏目：经济 -> 银行与金融
    入库表：dza_aps
    语言：阿拉伯语
    """

    name = "algeria_aps"


    country_code = "DZA"


    country = "阿尔及利亚"
    language = "en"
    strict_date_required = False
    source_timezone = "Africa/Algiers"
    start_date = "2026-01-01"
    allowed_domains = ["aps.dz"]
    # 当前 spider 对应的数据库表名。

    # 从 APS 经济栏目入口开始翻页抓取。
    start_urls = [
        "https://www.aps.dz/economie/banque-et-finances",
    ]

    fallback_content_selector = "article, main article, [itemprop='articleBody'], .article-content, .item-content, .entry-content, .post-content, .content, main"

    # 首次抓取的默认时间边界；后续会优先使用数据库里的最新时间做增量。

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

        # APS 列表页先收集文章链接，再继续找下一页。
        article_links = response.xpath(
            '//a[contains(@href, "/economie/banque-et-finances/")]/@href'
        ).getall()

        has_valid_item_in_window = False
        unique_links = []
        for href in article_links:
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
                continue
            has_valid_item_in_window = True
            unique_links.append(full_url)

        for article_url in unique_links:
            yield scrapy.Request(article_url, callback=self.parse_detail)

        if self._stop_pagination:
            return

        if has_valid_item_in_window:
            next_page = response.xpath(
                '//a[contains(@href, "/economie/banque-et-finances?start=")]/@href'
            ).get()
            if next_page:
                yield response.follow(next_page, callback=self.parse_listing)
                return

            pager_links = response.xpath(
                '//a[contains(@href, "/economie/banque-et-finances")]/@href'
            ).getall()
            next_url = self._pick_next_page(response.url, pager_links)
            if next_url:
                yield scrapy.Request(response.urljoin(next_url), callback=self.parse_listing)

    def parse_detail(self, response):
        item = self.auto_parse_item(response)
        if not item.get("title") or not item.get("content_plain"):
            return

        publish_time = item.get("publish_time")
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        # Spider-specific overrides
        item["author"] = "APS"
        item["section"] = "banque-et-finances"
        item["language"] = "ar"

        if len(item.get("content_plain", "")) > 100:
            yield item

    def _pick_next_page(self, current_url, hrefs):
        current_start = self._extract_start_offset(current_url)
        candidates = []

        for href in hrefs:
            start = self._extract_start_offset(href)
            if start is None:
                continue
            if start > current_start:
                candidates.append((start, href))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def _extract_start_offset(self, url):
        match = re.search(r"[?&]start=(\d+)", url or "")
        if match:
            return int(match.group(1))
        return 0 if "banque-et-finances" in (url or "") else None

