import scrapy
import re
from datetime import datetime
from scrapy_playwright.page import PageMethod
from news_scraper.spiders.base_spider import BaseNewsSpider


class MnMontsameSpider(BaseNewsSpider):
    """
    Spider for Mongolian National News Agency (Montsame) - Chinese edition.
    URL: https://www.montsame.mn/cn/more/103
    Table: mn_montsame_news
    Strategy: Full backfill on first run, incremental on subsequent runs.
    """
    name = "mn_montsame"

    country_code = 'MNG'

    country = '蒙古'
    allowed_domains = ["www.montsame.mn"]
    start_urls = ["https://www.montsame.mn/cn/more/103"]
    target_table = "mn_montsame_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": None,
            "news_scraper.middlewares.BatchDelayMiddleware": 600,
        },
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 2.0,
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", ".news-box", timeout=20000),
                    ]
                }
            )

    def parse(self, response):
        """Parse listing page and follow article links."""
        news_boxes = response.css('.news-box')
        found_any = False

        for box in news_boxes:
            link = box.css('a::attr(href)').get()
            if not link:
                continue

            if not link.startswith('http'):
                link = "https://www.montsame.mn" + link

            if link in self.scraped_urls:
                continue

            found_any = True
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
        if found_any:
            current_page = 1
            if '?page=' in response.url:
                match = re.search(r'page=(\d+)', response.url)
                if match:
                    current_page = int(match.group(1))

            if current_page < 100:
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
        title = response.css('h4.news-title::text, .news-title::text').get()
        if not title:
            title = response.css('title::text').get()

        # Date format: "2026-04-07 12:27:20"
        date_str = response.css('span.stat::text, .stat::text').get()
        pub_date = None
        if date_str:
            try:
                match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', date_str)
                if match:
                    pub_date = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
            except Exception:
                self.logger.warning(f"MN_DATE parse failed: {date_str}")

        if pub_date and not self.filter_date(pub_date):
            return

        # Body content
        content_nodes = response.css('.col-lg-9.col-sm-12 p::text').getall()
        content = "\n".join([c.strip() for c in content_nodes if len(c.strip()) > 30])

        if title and len(content) > 100:
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": pub_date,
                "author": "Montsame.mn",
                "language": "zh",
                "section": "Economy"
            }
