import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class BfbSpider(SmartSpider):
    name = 'bfb'
    source_timezone = 'Asia/Baku'
    
    country_code = 'AZE'
    country = '阿塞拜疆'
    language = 'az'
    
    allowed_domains = ['bfb.az']
    
    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    use_curl_cffi = True

    async def start(self):
        """Initial requests entry point."""
        for url in ['https://www.bfb.az/press-relizler']:
            yield scrapy.Request(url, callback=self.parse, dont_filter=True)
    
    # Azerbaijani month mapping (lowercase for matching)
    AZ_MONTHS = {
        'yanvar': 1, 'fevral': 2, 'mart': 3, 'aprel': 4,
        'may': 5, 'iyun': 6, 'iyul': 7, 'avqust': 8,
        'sentyabr': 9, 'oktyabr': 10, 'noyabr': 11, 'dekabr': 12
    }

    fallback_content_selector = ".main_press_container, .post_content, article"

    def parse(self, response):
        """Parses the press release list page."""
        items = response.css('.card')
        
        current_page_match = re.search(r'page=(\d+)', response.url)
        current_page = int(current_page_match.group(1)) if current_page_match else 1

        if not items:
            self.logger.warning(f"No items found on Page {current_page}")
            return

        has_valid_item_in_window = False

        for item in items:
            title_node = item.css('.post_title')
            date_node = item.css('.card-body .date')
            
            if title_node and date_node:
                # title = title_node.xpath('string()').get().strip()
                href = title_node.css('::attr(href)').get()
                date_str = date_node.xpath('string()').get().strip()
                
                # Preserve existing date localization logic
                publish_time_naive = self.parse_az_date(date_str)
                publish_time = self.parse_to_utc(publish_time_naive)
                
                article_url = response.urljoin(href)
                
                if not self.should_process(article_url, publish_time):
                    continue
                
                has_valid_item_in_window = True
                
                yield scrapy.Request(
                    url=article_url,
                    callback=self.parse_detail,
                    meta={'publish_time_hint': publish_time},
                    dont_filter=self.full_scan
                )

        # Pagination logic - continue if we found valid items in the current window
        if has_valid_item_in_window:
            next_link = response.xpath("//a[contains(text(), 'Sonrakı')]/@href").get()
            
            if next_link:
                yield response.follow(next_link, callback=self.parse)
            else:
                next_page = current_page + 1
                next_page_link = response.css(f'a.page-link[href*="page={next_page}"]::attr(href)').get()
                if next_page_link:
                    yield response.follow(next_page_link, callback=self.parse)
                else:
                    next_url = f"https://www.bfb.az/press-relizler?page={next_page}"
                    yield scrapy.Request(next_url, callback=self.parse)

    def parse_az_date(self, date_str):
        """Parses Azerbaijani date strings like '5 mart 2026'."""
        try:
            parts = date_str.lower().split()
            if len(parts) >= 3:
                day = int(parts[0])
                month_name = parts[1]
                year = int(parts[2])
                
                month = self.AZ_MONTHS.get(month_name)
                if month:
                    return datetime(year, month, day)
        except Exception as e:
            self.logger.error(f"Error parsing date {date_str}: {e}")
        return None

    def parse_detail(self, response):
        """Parses the article detail page using standardized SmartSpider extraction."""
        item = self.auto_parse_item(response)
        
        # Override/Set specific fields
        item['author'] = 'Baku Stock Exchange (BFB)'
        
        yield item
