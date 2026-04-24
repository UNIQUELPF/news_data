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
    start_urls = ['https://www.economy.gov.az/az/page/media/news']
    
    # Azerbaijani month mapping
    AZ_MONTHS = {
        'Yanvar': 1, 'Fevral': 2, 'Mart': 3, 'Aprel': 4,
        'May': 5, 'İyun': 6, 'İyul': 7, 'Avqust': 8,
        'Sentyabr': 9, 'Oktyabr': 10, 'Noyabr': 11, 'Dekabr': 12
    }

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
                title = title_node.xpath('string()').get().strip()
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
                    meta={'title': title, 'publish_time': publish_time},
                    dont_filter=True
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
        item = self.auto_parse_item(
            response,
            title_xpath=None,
            publish_time_xpath=None
        )
        
        # Override/Set specific fields
        item['title'] = response.meta.get('title') or item.get('title')
        item['publish_time'] = response.meta.get('publish_time') or item.get('publish_time')
        item['author'] = 'Ministry of Economy of the Republic of Azerbaijan'
        
        yield item

