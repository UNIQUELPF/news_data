import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class EthiopiaNBESpider(SmartSpider):
    name = "ethiopia_nbe"
    country_code = 'ETH'
    country = '埃塞俄比亚'
    allowed_domains = ["nbe.gov.et"]
    target_table = "ethi_nbe"
    
    source_timezone = 'Africa/Cairo' # Ethiopia is UTC+3
    fallback_content_selector = ".elementor-widget-theme-post-content, .entry-content, article, main"

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def start_requests(self):
        url = "https://nbe.gov.et/all-news/"
        yield scrapy.Request(url, callback=self.parse_list, dont_filter=True)

    def parse_list(self, response):
        # Elementor typically uses these classes for posts
        cards = response.css('article, .elementor-post')
        if not cards:
            # Fallback to simple links
            links = response.css('a[href*="/nbe_news/"]::attr(href)').getall()
            for link in list(dict.fromkeys(links)):
                url = response.urljoin(link)
                if self.should_process(url, None):
                    yield scrapy.Request(url, callback=self.parse_detail)
            return

        has_valid_item_in_window = False
        for card in cards:
            link_el = card.css('a[href*="/nbe_news/"]::attr(href)').get()
            if not link_el:
                continue
                
            url = response.urljoin(link_el)
            
            # Try to extract date from the card
            date_text = card.css('.elementor-post-date::text, .elementor-post-info__item--type-date::text, time::attr(datetime)').get()
            
            publish_time = None
            if date_text:
                import dateparser
                publish_time = dateparser.parse(date_text, settings={'TIMEZONE': 'UTC'})
            
            publish_time_utc = self.parse_to_utc(publish_time) if publish_time else None

            if self.should_process(url, publish_time_utc):
                has_valid_item_in_window = True
                meta_dict = {'publish_time_hint': publish_time_utc}
                yield scrapy.Request(url, callback=self.parse_detail, meta=meta_dict)

        if has_valid_item_in_window:
            pagination = response.css('a.page-numbers::attr(href)').getall()
            for p_url in pagination:
                if "/all-news/" in p_url:
                    yield scrapy.Request(response.urljoin(p_url), callback=self.parse_list)

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//meta[@property='og:title']/@content | //h1/text()",
            publish_time_xpath="//span[contains(@class, 'elementor-post-info__item--type-date')]//time/text() | //time/text()",
        )
        
        # Ensure the main image is captured
        og_image = response.xpath("//meta[@property='og:image']/@content").get()
        if og_image:
            if not item.get('images'):
                item['images'] = []
            if og_image not in item['images']:
                item['images'].insert(0, og_image)

        # Determine language based on content
        text_for_lang = (item.get('title') or '') + (item.get('content_plain') or '')
        if re.search(r"[\u1200-\u137F]", text_for_lang):
            item['language'] = 'am'
        else:
            item['language'] = 'en'

        # Stop processing if older than cutoff (unless full_scan)
        if not self.full_scan and item['publish_time'] and item['publish_time'] < self.cutoff_date:
            self.logger.info(f"Skipping old article: {response.url} (Date: {item['publish_time']})")
            return

        item['author'] = "National Bank of Ethiopia"
        item['country_code'] = self.country_code
        item['country'] = self.country
        yield item
