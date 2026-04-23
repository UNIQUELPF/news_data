import scrapy
import dateparser
import re
from news_scraper.spiders.smart_spider import SmartSpider

class AlbaniaSpider(SmartSpider):
    """
    Modernized Albania Prime Minister's Office Spider.
    Note: Site has strong protection, may require specific custom_settings.
    """
    name = 'albania'
    source_timezone = 'Europe/Tirane'
    
    country_code = 'ALB'
    country = '阿尔巴尼亚'
    
    allowed_domains = ['kryeministria.al']
    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    use_curl_cffi = True

    async def start(self):
        for url in ['https://www.kryeministria.al/newsrooms/lajme/']:
            yield scrapy.Request(url, callback=self.parse, dont_filter=True)

    fallback_content_selector = "article, .body-content, div.container1"

    def parse(self, response):
        """Parses the news list page."""
        articles = response.css('article.news-item')
        self.logger.info(f"Scraping {len(articles)} articles from {response.url}")

        has_valid_item_in_window = False
        for article in articles:
            title_node = article.css('a.news-item__title')
            date_node = article.css('time.posted-on')
            
            if title_node and date_node:
                url = response.urljoin(title_node.attrib.get('href'))
                date_str = date_node.xpath('string()').get().strip()
                # Clean prefix "POSTUAR MË:" or similar
                date_str = re.sub(r'POSTUAR MË:\s*', '', date_str, flags=re.IGNORECASE)
                
                # Parse date for early stopping
                dt_local = dateparser.parse(date_str, languages=['sq', 'en'])
                publish_time = self.parse_to_utc(dt_local)
                
                if not self.should_process(url, publish_time):
                    continue
                
                has_valid_item_in_window = True
                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    dont_filter=self.full_scan,
                    meta={'publish_time_hint': publish_time}
                )

        if has_valid_item_in_window:
            next_page = response.css('a.nextpostslink::attr(href)').get()
            if next_page:
                yield response.follow(next_page, callback=self.parse, dont_filter=True)

    def parse_detail(self, response):
        """Standardized detail parsing."""
        yield self.auto_parse_item(response)

