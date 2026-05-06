import scrapy
import re
from scrapy_playwright.page import PageMethod
from news_scraper.spiders.smart_spider import SmartSpider


class MnMontsameSpider(SmartSpider):
    """
    Spider for Mongolian National News Agency (Montsame) - Chinese edition.
    URL: https://www.montsame.mn/cn/more/103
    Strategy: Full backfill on first run, incremental on subsequent runs.
    """
    name = "mn_montsame"
    country_code = 'MNG'
    country = '蒙古'
    language = 'zh'
    source_timezone = 'Asia/Ulaanbaatar'
    allowed_domains = ["www.montsame.mn"]
    start_urls = ["https://www.montsame.mn/cn/more/103"]
    fallback_content_selector = '.col-lg-9.col-sm-12'
    strict_date_required = False
    MAX_PAGES = 100

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": None,
            "news_scraper.middlewares.BatchDelayMiddleware": 600,
        },
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 2.0,
    }

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", ".news-box", timeout=20000),
                    ]
                },
                dont_filter=True,
            )

    def parse(self, response):
        """Parse listing page and follow article links."""
        if self._stop_pagination:
            return
        news_boxes = response.css('.news-box')
        has_valid_item_in_window = False

        for box in news_boxes:
            link = box.css('a::attr(href)').get()
            if not link:
                continue

            if not link.startswith('http'):
                link = "https://www.montsame.mn" + link

            if not self.should_process(link):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                link,
                callback=self.parse_article,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", ".news-title", timeout=20000),
                    ]
                }
            )

        # Pagination: ?page=X
        if has_valid_item_in_window:
            current_page = 1
            if '?page=' in response.url:
                match = re.search(r'page=(\d+)', response.url)
                if match:
                    current_page = int(match.group(1))

            if current_page < self.MAX_PAGES:
                next_page_url = f"https://www.montsame.mn/cn/more/103?page={current_page + 1}"
                yield scrapy.Request(
                    next_page_url,
                    callback=self.parse,
                    meta={
                        "playwright": True,
                        "playwright_page_methods": [
                            PageMethod("wait_for_selector", ".news-box", timeout=20000),
                        ]
                    }
                )

    def parse_article(self, response):
        """Extract article data from detail page."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h4[@class='news-title']/text() | //*[@class='news-title']/text()",
        )

        # 手动处理发布日期，日期格式："2026-04-07 12:27:20"
        date_str = response.css('span.stat::text, .stat::text').get()
        pub_date = None
        if date_str:
            match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', date_str)
            if match:
                pub_date = self.parse_date(match.group(1))

        if pub_date:
            item['publish_time'] = pub_date

        item['author'] = 'Montsame.mn'
        item['section'] = 'Economy'

        if pub_date and not self.should_process(response.url, pub_date):
            self._stop_pagination = True
            return

        if item.get('content_plain') and len(item['content_plain']) > 100:
            yield item
