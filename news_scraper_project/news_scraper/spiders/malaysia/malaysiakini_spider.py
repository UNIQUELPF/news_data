import json
from datetime import datetime

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class MalaysiakiniSpider(SmartSpider):
    name = "malaysia_malaysiakini"

    country_code = "MYS"
    country = "马来西亚"
    language = "en"
    source_timezone = "Asia/Kuala_Lumpur"
    start_date = "2026-01-01"
    allowed_domains = ["malaysiakini.com"]

    use_curl_cffi = True
    fallback_content_selector = "article"

    # Listing API only provides SIDs and titles -- no date_pub.
    # Date filtering happens on the detail page via auto_parse_item + should_process.
    strict_date_required = False

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS': 16,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 500,
        },
    }

    API_URL = "https://www.malaysiakini.com/api/en/latest/news/{}?limit=50"
    MAX_PAGES = 500

    def start_requests(self):
        yield scrapy.Request(
            self.API_URL.format(1),
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True,
        )

    def parse_list(self, response):
        page = response.meta['page']

        try:
            data = json.loads(response.text)
        except Exception:
            self.logger.error("Failed to parse API JSON")
            return

        stories = data.get('stories', [])
        if not stories:
            self.logger.info(f"No more stories on page {page}")
            return

        self.logger.info(f"Page {page}: found {len(stories)} stories")

        has_valid_item_in_window = False

        for story in stories:
            sid = story.get('sid')
            if not sid:
                continue

            # Language filter: only crawl English articles
            story_lang = story.get('language') or story.get('lang')
            if story_lang and story_lang != 'en':
                continue

            url = f"https://www.malaysiakini.com/news/{sid}"
            title_hint = story.get('title')

            # No should_process here because the listing API omits date_pub.
            # Date filtering happens in parse_article after auto_parse_item extracts it.
            has_valid_item_in_window = True

            yield scrapy.Request(
                url,
                callback=self.parse_article,
                meta={
                    'title_hint': title_hint,
                },
                dont_filter=True,
            )

        # Pagination with circuit breaker (uses MAX_PAGES as safety cap since
        # listing has no per-item date for window-based circuit breaking).
        if has_valid_item_in_window and page < self.MAX_PAGES:
            next_page = page + 1
            yield scrapy.Request(
                self.API_URL.format(next_page),
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True,
            )

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )

        if not self.should_process(response.url, item.get('publish_time')):
            return

        item['author'] = item.get('author') or 'Malaysiakini'
        item['section'] = item.get('section') or 'news'

        yield item
