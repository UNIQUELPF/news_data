import scrapy
import re
from news_scraper.spiders.smart_spider import SmartSpider


class GrMinfinSpider(SmartSpider):
    name = 'gr_minfin'
    source_timezone = 'Europe/Athens'

    country_code = 'GRC'
    country = '希腊'
    language = 'el'
    use_curl_cffi = False

    allowed_domains = ['minfin.gov.gr']

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1,
        "AUTOTHROTTLE_ENABLED": True,
    }

    fallback_content_selector = '.elementor-widget-theme-post-content, .entry-content, .post-content, article .elementor-widget-container'

    # 财政部新闻大厅
    base_url = 'https://minfin.gov.gr/grafeio-typou/anakoinoseis-typou-el/page/{}/'

    def start_requests(self):
        yield scrapy.Request(
            self.base_url.format(1),
            callback=self.parse,
            dont_filter=True
        )

    def parse(self, response):
        """Parse listing page with date-based circuit breaker."""
        # Iterate over <article class="elementor-post"> containers, not loose links.
        # Each article consistently has both the link (.elementor-post__title a)
        # and the date (.elementor-post-date) as direct descendants.
        articles = response.css('article.elementor-post')

        has_valid_item_in_window = False

        # Extract current page number from URL; page 1 301-redirects to root
        current_page = 1
        page_match = re.search(r'/page/(\d+)/', response.url)
        if page_match:
            current_page = int(page_match.group(1))

        for article in articles:
            link = article.css('.elementor-post__title a::attr(href)').get()
            if not link:
                continue

            # Date is in .elementor-post__meta-data > .elementor-post-date
            # e.g. "<span class="elementor-post-date">2 Μαΐου 2026</span>"
            date_str = article.css('.elementor-post-date::text').get()
            publish_time = self.parse_date(date_str.strip()) if date_str else None

            if not self.should_process(link, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                link,
                callback=self.parse_detail,
                dont_filter=self.full_scan,
                meta={'publish_time_hint': publish_time}
            )

        # Pagination: only driven by circuit breaker (no hardcoded page limit)
        if has_valid_item_in_window:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                dont_filter=True,
            )

    def parse_detail(self, response):
        """Parse article detail page using auto_parse_item."""
        item = self.auto_parse_item(
            response,
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )

        item['author'] = 'Ministry of Finance Greece'
        item['section'] = 'Press Office'

        yield item
