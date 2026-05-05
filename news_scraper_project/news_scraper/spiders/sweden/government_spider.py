import scrapy
from datetime import datetime
import re
from news_scraper.spiders.smart_spider import SmartSpider

class GovernmentSESpider(SmartSpider):
    name = "se_government"
    source_timezone = 'Europe/Stockholm'

    country_code = 'SWE'
    country = '瑞典'
    language = 'en'
    strict_date_required = True

    allowed_domains = ['government.se']
    use_curl_cffi = True

    fallback_content_selector = "div.article__body"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS': 2,
    }

    async def start(self):
        yield scrapy.Request(
            "https://www.government.se/government-policy/economic-policy/",
            callback=self.parse,
            dont_filter=True
        )

    def parse(self, response):
        links = response.css('div.sortcompact.sortextended a::attr(href)').getall()
        has_valid_item_in_window = False

        for link in links:
            if not link.startswith('http'):
                link = response.urljoin(link)

            # Extract date from URL pattern: /articles/YYYY/MM/
            publish_time = None
            date_match = re.search(r'/articles/(\d{4})/(\d{2})/', link)
            if date_match:
                try:
                    dt_obj = datetime.strptime(f"{date_match.group(1)}-{date_match.group(2)}-01", '%Y-%m-%d')
                    publish_time = self.parse_to_utc(dt_obj)
                except ValueError:
                    pass

            if not self.should_process(link, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                link,
                callback=self.parse_detail,
                meta={"publish_time_hint": publish_time}
            )

        if has_valid_item_in_window:
            next_page = response.css('li.nav--pagination__next a::attr(href)').get()
            if next_page:
                yield response.follow(next_page, self.parse)

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            publish_time_xpath="//meta[@property='article:published_time']/@content"
        )

        # Fallback: URL-based date extraction
        if not item.get('publish_time'):
            date_match = re.search(r'/articles/(\d{4})/(\d{2})/', response.url)
            if date_match:
                try:
                    dt_obj = datetime.strptime(f"{date_match.group(1)}-{date_match.group(2)}-01", '%Y-%m-%d')
                    item['publish_time'] = self.parse_to_utc(dt_obj)
                except ValueError:
                    pass

        item['author'] = 'Government of Sweden'
        item['section'] = 'Economic Policy'

        yield item
