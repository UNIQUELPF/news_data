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
        news_boxes = response.css('.news-box')
        valid_links = []

        for box in news_boxes:
            link = box.css('a::attr(href)').get()
            if not link:
                continue

            if not link.startswith('http'):
                link = "https://www.montsame.mn" + link

            if not self.should_process(link):
                continue
            valid_links.append(link)

        current_page = 1
        if '?page=' in response.url:
            match = re.search(r'page=(\d+)', response.url)
            if match:
                current_page = int(match.group(1))

        if not valid_links:
            self.logger.info(f"[{self.name}] No valid links to process on page {current_page}. Stopping.")
            return

        state = {
            'pending_count': len(valid_links),
            'dates': [],
            'page': current_page,
            'response_url': response.url
        }

        for url in valid_links:
            yield scrapy.Request(
                url,
                callback=self.parse_article,
                errback=self._handle_detail_error,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", ".news-title", timeout=20000),
                    ],
                    "shared_state": state
                }
            )

    def _check_next_page(self, state, response_url):
        page = state['page']
        parsed_dates = [d for d in state['dates'] if d is not None]

        if parsed_dates and all(d < self.cutoff_date for d in parsed_dates):
            self.logger.info(f"[{self.name}] All articles on page {page} are older than cutoff {self.cutoff_date}. Stopping pagination.")
            return

        if page < self.MAX_PAGES:
            next_page_url = f"https://www.montsame.mn/cn/more/103?page={page + 1}"
            self.logger.info(f"Continuing to page {page + 1}: {next_page_url}")
            yield scrapy.Request(
                next_page_url,
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", ".news-box", timeout=20000),
                    ],
                    "page": page + 1
                }
            )

    def _handle_detail_error(self, failure):
        self.logger.error(f"Detail request failed: {failure.value}")
        state = failure.request.meta.get('shared_state')
        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state, state['response_url']):
                    yield req

    def parse_article(self, response):
        """Extract article data from detail page."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h4[@class='news-title']/text() | //*[@class='news-title']/text()",
        )
        state = response.meta.get('shared_state')

        # 手动处理发布日期，日期格式："2026-04-07 12:27:20"
        date_str = response.css('span.stat::text, .stat::text').get()
        pub_date = None
        if date_str:
            match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', date_str)
            if match:
                pub_date = self.parse_date(match.group(1))

        if state:
            state['dates'].append(pub_date)

        if item and self.should_process(response.url, pub_date):
            if pub_date:
                item['publish_time'] = pub_date

            item['author'] = 'Montsame.mn'
            item['section'] = 'Economy'

            if item.get('content_plain') and len(item['content_plain']) > 100:
                yield item

        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state, response.url):
                    yield req
