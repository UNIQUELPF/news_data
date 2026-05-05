import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class TmFineconomicSpider(SmartSpider):
    name = "tm_fineconomic"
    source_timezone = 'Asia/Ashgabat'

    country_code = 'TKM'
    country = '土库曼斯坦'
    language = 'tm'

    allowed_domains = ['fineconomic.gov.tm']

    # 列表页入口
    base_url = 'https://fineconomic.gov.tm/news/all?page={}'

    # European date format: Day.Month.Year
    dateparser_settings = {'DATE_ORDER': 'DMY'}

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_TIMEOUT': 30,
    }

    use_curl_cffi = True
    strict_date_required = True
    fallback_content_selector = "div.in-news__content--text"

    async def start(self):
        """Initial requests entry point."""
        yield scrapy.Request(self.base_url.format(1), callback=self.parse, dont_filter=True)

    def parse(self, response):
        """
        Parse listing page with date-based circuit breaker.
        Dates are extractable from URL patterns: /habar/xxx-19.03.2026
        """
        links = response.css('a[href*="/habar/"]::attr(href)').getall()
        current_page = response.meta.get('page', 1)

        has_valid_item_in_window = False

        for link in set(links):
            # Extract date from URL: /habar/xxx-19.03.2026
            publish_time = None
            try:
                date_str = link.rstrip('/').split('-')[-1]
                if '.' in date_str and len(date_str) == 10:
                    dt_obj = datetime.strptime(date_str, '%d.%m.%Y')
                    publish_time = self.parse_to_utc(dt_obj)
            except Exception:
                pass

            full_url = response.urljoin(link)
            if not self.should_process(full_url, publish_time):
                continue

            has_valid_item_in_window = True
            yield response.follow(
                link,
                self.parse_article,
                meta={"publish_time_hint": publish_time}
            )

        # Pagination circuit breaker: stop when no items are within the window
        if has_valid_item_in_window:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        """Parse article detail page using standardized SmartSpider extraction."""
        item = self.auto_parse_item(
            response,
            title_xpath="string(//div[contains(@class, 'in-news__content--title')])",
            publish_time_xpath="//div[contains(@class, 'in-news__content--date')]/text()"
        )

        # Fallback title from h1
        if not item.get('title'):
            item['title'] = response.css('h1::text').get('').strip()

        item['author'] = 'Ministry of Finance and Economy of Turkmenistan'
        item['section'] = 'Economics'

        yield item
