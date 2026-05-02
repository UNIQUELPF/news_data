import scrapy
import dateparser
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class IranMehrEnSpider(SmartSpider):
    name = 'iran_mehr_en'
    source_timezone = 'Asia/Tehran'
    fallback_content_selector = ".item-text"
    country_code = 'IRN'
    country = '伊朗'
    language = 'en'
    
    allowed_domains = ['en.mehrnews.com']
    
    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    use_curl_cffi = True

    async def start(self):
        # Economy section
        yield scrapy.Request(url="https://en.mehrnews.com/service/economy", callback=self.parse, dont_filter=True)

    def parse(self, response):
        # Extract news items
        news_items = response.css('li.news')
        self.logger.info(f"Found {len(news_items)} news items on {response.url}")

        has_valid_item_in_window = False
        for news in news_items:
            link = news.css('h3 a::attr(href)').get() or news.css('figure a::attr(href)').get()
            if not link:
                continue
            
            url = response.urljoin(link)
            
            # Extract date from the summary text if possible
            # Example: "TEHRAN, Apr. 29 (MNA) – ..."
            summary_text = news.css('p::text').get('')
            publish_time = None
            if '–' in summary_text:
                date_part = summary_text.split('–')[0] # "TEHRAN, Apr. 29 (MNA) "
                # Try to parse date from "Apr. 29"
                import re
                date_match = re.search(r'([A-Z][a-z]{2}\.? \d{1,2})', date_part)
                if date_match:
                    date_str = date_match.group(1)
                    # Add current year if not present
                    publish_time = dateparser.parse(date_str)
                    if publish_time:
                        publish_time = self.parse_to_utc(publish_time)

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
                dont_filter=self.full_scan,
                meta={'publish_time_hint': publish_time}
            )

        if has_valid_item_in_window:
            # Pagination
            # The original code used a complex archive URL, but often there's a "Next" button.
            # Let's check for a standard pagination link first.
            next_page = response.css('li.next a::attr(href)').get()
            if next_page:
                yield scrapy.Request(response.urljoin(next_page), callback=self.parse, dont_filter=True)
            else:
                # Fallback to the archive URL logic if needed
                current_page_num = response.meta.get('page_num', 1)
                next_page_num = current_page_num + 1
                next_page_url = f"https://en.mehrnews.com/page/archive.xhtml?mn=130&dt=1&pi={next_page_num}"
                yield scrapy.Request(url=next_page_url, callback=self.parse, dont_filter=True, meta={'page_num': next_page_num})

    def parse_detail(self, response):
        # Standard auto-parsing
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class, 'title')]/text()",
            publish_time_xpath="//div[contains(@class, 'item-date')]//span/text()",
        )
        
        # Prioritize og:image
        og_image = response.xpath("//meta[@property='og:image']/@content").get()
        if og_image:
            if 'images' not in item or not item['images']:
                item['images'] = [og_image]
            elif og_image not in item['images']:
                item['images'].insert(0, og_image)
        
        # Clean images
        if 'images' in item and item['images']:
            item['images'] = [img if isinstance(img, str) else img.get('url') for img in item['images'] if img]

        item['section'] = 'Economy'
        
        yield item
