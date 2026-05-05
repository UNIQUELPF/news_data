import scrapy
import re
from news_scraper.spiders.smart_spider import SmartSpider


class UkMoneyweekSpider(SmartSpider):
    name = "uk_moneyweek"
    source_timezone = 'Europe/London'

    country_code = 'GBR'
    country = '英国'
    language = 'en'
    allowed_domains = ["moneyweek.com"]

    # No dates on listing page; strict mode would block all listing items
    strict_date_required = False
    fallback_content_selector = "div.article__body"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1
    }

    use_curl_cffi = True

    async def start(self):
        yield scrapy.Request(
            "https://moneyweek.com/economy/uk-economy",
            callback=self.parse_listing,
            dont_filter=True
        )

    def parse_listing(self, response):
        """Parse listing page with article links and sequential pagination."""
        article_links = response.css(
            'a.listing__link::attr(href), h2.listing__title a::attr(href)'
        ).getall()

        has_valid_item_in_window = False
        for link in list(set(article_links)):
            if self.should_process(link):
                has_valid_item_in_window = True
                yield response.follow(link, self.parse_detail)

        if has_valid_item_in_window:
            current_match = re.search(r'[?&]page=(\d+)', response.url)
            current_page = int(current_match.group(1)) if current_match else 1

            next_url = (
                f"https://moneyweek.com/economy/uk-economy"
                f"?page={current_page + 1}"
            )
            yield scrapy.Request(
                next_url, callback=self.parse_listing
            )

    def parse_detail(self, response):
        """Parse article detail page using SmartSpider auto extraction."""
        item = self.auto_parse_item(response)
        item['author'] = response.css(
            'meta[name="author"]::attr(content)'
        ).get("MoneyWeek")
        item['section'] = "UK Economy"

        yield item
