import re
from datetime import datetime

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class MalayMailSpider(SmartSpider):
    name = "malaysia_malaymail"

    country_code = "MYS"
    country = "马来西亚"
    language = "en"
    source_timezone = "Asia/Kuala_Lumpur"
    start_date = "2026-01-01"
    use_curl_cffi = True
    fallback_content_selector = "div.article-body, div.item-content"

    allowed_domains = ["malaymail.com"]

    # Money section
    BASE_URL = "https://www.malaymail.com/morearticles/money?page={page}"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS': 8,
    }

    def start_requests(self):
        yield scrapy.Request(
            self.BASE_URL.format(page=1),
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True,
        )

    def parse_list(self, response):
        page = response.meta['page']

        items = response.css('div.article-item')
        if not items:
            items = response.xpath("//h2/parent::div")

        if not items:
            self.logger.info(f"No more items on page {page}")
            return

        self.logger.info(f"Page {page}: found {len(items)} items")

        has_valid_item_in_window = False

        for item in items:
            url = item.css('h2 a::attr(href)').get()
            if not url:
                continue
            url = response.urljoin(url)

            # Extract date from URL pattern: /news/money/YYYY/MM/DD/...
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
            publish_time = None
            if date_match:
                year, month, day = date_match.groups()
                try:
                    publish_time = self.parse_to_utc(
                        datetime(int(year), int(month), int(day))
                    )
                except ValueError:
                    pass

            if not self.should_process(url, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_article,
                meta={'publish_time_hint': publish_time},
                dont_filter=True,
            )

        # Pagination
        if has_valid_item_in_window and len(items) > 0:
            next_page = page + 1
            if next_page <= 1000:  # Safety cap
                yield scrapy.Request(
                    self.BASE_URL.format(page=next_page),
                    callback=self.parse_list,
                    meta={'page': next_page},
                    dont_filter=True,
                )

    def parse_article(self, response):
        item = self.auto_parse_item(response)

        item['author'] = item.get('author') or 'Malay Mail'
        item['section'] = 'Money'

        # Final safety check on publish_time (V2 requirement)
        if not self.full_scan and item.get('publish_time'):
            if item['publish_time'] < self.cutoff_date:
                return

        yield item
