import scrapy
from datetime import datetime
import re
from news_scraper.spiders.smart_spider import SmartSpider

class GrTovimaSpider(SmartSpider):
    name = 'gr_tovima'
    source_timezone = 'Europe/Athens'

    country_code = 'GRC'
    country = '希腊'
    language = 'el'

    allowed_domains = ['tovima.gr']

    use_curl_cffi = True
    fallback_content_selector = 'article, .post-content'

    async def start(self):
        """Initial requests entry point."""
        yield scrapy.Request(
            'https://www.tovima.gr/category/finance/page/1/',
            callback=self.parse,
            dont_filter=True
        )

    def parse(self, response):
        """Parse listing page: extract article links with URL-embedded dates."""
        links = response.css(
            'a.is-block::attr(href), a.columns.is-mobile.is-multiline::attr(href)'
        ).getall()

        has_valid_item_in_window = False

        for link in links:
            # Extract date from URL pattern: /YYYY/MM/DD/
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', link)
            publish_time = None
            if date_match:
                year, month, day = date_match.groups()
                try:
                    url_date = datetime(year=int(year), month=int(month), day=int(day))
                    publish_time = self.parse_to_utc(url_date)
                except ValueError:
                    pass

            # Standard V2 deduplication and incremental check
            if not self.should_process(link, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                link,
                callback=self.parse_detail,
                dont_filter=self.full_scan
            )

        # Pagination: continue while we found items within the date window
        if has_valid_item_in_window:
            current_page = response.meta.get('page', 1)
            next_page = current_page + 1
            yield scrapy.Request(
                f'https://www.tovima.gr/category/finance/page/{next_page}/',
                callback=self.parse,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_detail(self, response):
        """Parse article detail page using standardized SmartSpider extraction."""
        item = self.auto_parse_item(response)

        # Override specific fields
        item['author'] = 'To Vima Finance'
        item['section'] = 'Finance'

        yield item
