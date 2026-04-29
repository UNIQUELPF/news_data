import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class EconomySpider(SmartSpider):
    name = 'economy'
    source_timezone = 'Asia/Baku'
    
    country_code = 'AZE'
    country = '阿塞拜疆'
    language = 'az'
    
    allowed_domains = ['economy.gov.az']
    
    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    use_curl_cffi = True

    async def start(self):
        """Initial requests entry point."""
        for url in ['https://www.economy.gov.az/az/page/media/news']:
            yield scrapy.Request(url, callback=self.parse, dont_filter=True)
    
    # Azerbaijani month mapping
    AZ_MONTHS = {
        'Yanvar': 1, 'Fevral': 2, 'Mart': 3, 'Aprel': 4,
        'May': 5, 'İyun': 6, 'İyul': 7, 'Avqust': 8,
        'Sentyabr': 9, 'Oktyabr': 10, 'Noyabr': 11, 'Dekabr': 12
    }

    fallback_content_selector = ".content-block__text, article, .body-text"

    def parse(self, response):
        """Parses the news list page."""
        items = response.css('.news-section__item')
        if not items:
            self.logger.warning(f"No items found on {response.url}")
            return

        has_valid_item_in_window = False

        for item in items:
            title_node = item.css('.news-section__title')
            date_node = item.css('.news-section__date')
            
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
            current_page_match = re.search(r'page=(\d+)', response.url)
            current_page = int(current_page_match.group(1)) if current_page_match else 1
            next_page = current_page + 1
            
            next_page_link = response.css(f'ul.pagination li a[href*="page={next_page}"]::attr(href)').get()
            
            if next_page_link:
                yield response.follow(next_page_link, callback=self.parse)
            else:
                next_url = f"https://www.economy.gov.az/az/page/media/news?page={next_page}"
                yield scrapy.Request(next_url, callback=self.parse)

    def parse_az_date(self, date_str):
        """Parses Azerbaijani date strings like 'Mart 05, 2026 15:00'."""
        try:
            clean_str = date_str.replace(',', '').replace('  ', ' ')
            parts = clean_str.split(' ')
            if len(parts) >= 4:
                month_name = parts[0]
                day = int(parts[1])
                year = int(parts[2])
                time_parts = parts[3].split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                
                month = self.AZ_MONTHS.get(month_name)
                if month:
                    return datetime(year, month, day, hour, minute)
        except Exception as e:
            self.logger.error(f"Error parsing date {date_str}: {e}")
        return None

    def parse_detail(self, response):
        """Parses the article detail page using standardized SmartSpider extraction."""
        item = self.auto_parse_item(response)
        
        # Override/Set specific fields
        item['author'] = 'Ministry of Economy of the Republic of Azerbaijan'
        
        yield item
