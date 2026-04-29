import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class EthiopiaAddisChamberSpider(SmartSpider):
    name = "ethiopia_addischamber"
    country_code = 'ETH'
    country = '埃塞俄比亚'
    allowed_domains = ["addischamber.com"]
    target_table = "ethi_addischamber"
    
    language = 'en'
    source_timezone = 'Africa/Cairo' # Ethiopia is UTC+3
    fallback_content_selector = ".entry-content, article, .elementor-widget-theme-post-content, #main"

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def start_requests(self):
        url = "https://addischamber.com/news/"
        yield scrapy.Request(url, callback=self.parse_list, dont_filter=True, meta={'page': 1})

    def _extract_date(self, text):
        if not text:
            return None
        # Match "Jan 1, 2024" or "January 1, 2024"
        match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, 20\d\d', text)
        if match:
            import dateparser
            return dateparser.parse(match.group(), settings={'TIMEZONE': 'UTC'})
        return None

    def parse_list(self, response):
        blocks = response.css('div.ultp-block-item')
        if not blocks:
            self.logger.warning(f"No blocks found on {response.url}")
            return

        has_valid_item_in_window = False
        for block in blocks:
            a_tag = block.css('h3 a, .ultp-block-title a, h2 a')
            if not a_tag:
                continue
                
            href = a_tag.attrib.get('href', '')
            if not href or '/category/' in href or '/news/' == href.strip('/') or href.endswith('/news/'):
                continue

            url = response.urljoin(href)
            
            # Extract date from block text
            date_text = "".join(block.xpath('.//text()').getall())
            publish_time = self._extract_date(date_text)
            publish_time_utc = self.parse_to_utc(publish_time) if publish_time else None

            if self.should_process(url, publish_time_utc):
                has_valid_item_in_window = True
                meta_dict = {'publish_time_hint': publish_time_utc}
                yield scrapy.Request(url, callback=self.parse_detail, meta=meta_dict)

        if has_valid_item_in_window:
            page = response.meta.get('page', 1)
            if page < 50: # safety limit
                next_page = page + 1
                next_url = f"https://addischamber.com/news/page/{next_page}/"
                yield scrapy.Request(next_url, callback=self.parse_list, meta={'page': next_page})

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class, 'entry-title')]/text() | //h1/text()",
            publish_time_xpath=None # Handled by hint or auto
        )
        
        if not item['publish_time']:
            # Try extracting from detail page text if hint missing
            all_text = "".join(response.xpath("//body//text()").getall()[:2000])
            item['publish_time'] = self.parse_to_utc(self._extract_date(all_text))

        # Stop processing if older than cutoff (unless full_scan)
        if not self.full_scan and item['publish_time'] and item['publish_time'] < self.cutoff_date:
            return

        item['author'] = "Addis Chamber"
        yield item
