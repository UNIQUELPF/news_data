import re
from datetime import datetime
import scrapy
from scrapy.http import FormRequest
from news_scraper.spiders.smart_spider import SmartSpider

class SaudiMcSpider(SmartSpider):
    """
    Spider for Saudi Ministry of Commerce (mc.gov.sa).
    Uses ASP.NET FormRequest via __doPostBack for pagination.
    """
    name = "saudi_mc"
    country_code = 'SAU'
    country = '沙特阿拉伯'
    language = 'en'
    source_timezone = 'UTC' # Assuming UTC or local time is handled by dateparser
    fallback_content_selector = 'div.ms-rtestate-field, [id*="newsInner"]'

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "DOWNLOAD_FAIL_ON_DATALOSS": False
    }

    async def start(self):
        yield scrapy.Request("https://mc.gov.sa/en/mediacenter/News/Pages/default.aspx", callback=self.parse, dont_filter=True)

    def parse(self, response):
        news_items = response.css('div.newsListItem')
        self.logger.info(f"Loaded page with {len(news_items)} news items. URL: {response.url}")

        if not news_items:
            return

        has_valid_item_in_window = False
        for item in news_items:
            # Extract date
            date_str_raw = item.css('[class*="date"] *::text, [class*="Date"] *::text, [class*="date"]::text, [class*="Date"]::text').getall()
            date_str = " ".join(date_str_raw).replace("\r", " ").replace("\n", " ").strip()
            publish_time = self.parse_date(date_str)
            
            link = item.css('a::attr(href)').get()
            if not link:
                continue

            url = response.urljoin(link)
            
            if not self.should_process(url, publish_time):
                if publish_time and publish_time < self.cutoff_date:
                    self.logger.info(f"Hit date boundary at {publish_time}. Stopping pagination.")
                    has_valid_item_in_window = False
                    break
                continue
                
            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={'publish_time_hint': publish_time}
            )

        # Pagination using __doPostBack
        if has_valid_item_in_window:
            next_link = response.xpath('//a[contains(@class, "Next") or contains(text(), "Next")]/@href').get()
            if next_link and "__doPostBack" in next_link:
                match = re.search(r"__doPostBack\('(.*?)',''\)", next_link)
                if match:
                    event_target = match.group(1)
                    self.logger.info(f"Paginating to next page via event target: {event_target}")
                    yield FormRequest.from_response(
                        response,
                        formdata={
                            '__EVENTTARGET': event_target,
                            '__EVENTARGUMENT': ''
                        },
                        callback=self.parse,
                        dont_filter=True
                    )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//span[contains(@class, 'date')]/text()",
        )
        item['author'] = "Ministry of Commerce"
        item['section'] = "News"
        yield item
