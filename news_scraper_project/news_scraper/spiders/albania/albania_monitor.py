import scrapy
import dateparser
import re
from news_scraper.spiders.smart_spider import SmartSpider

class AlbaniaMonitorSpider(SmartSpider):
    """
    Modernized Albania Monitor Spider.
    Inherits from SmartSpider for automated state and content handling.
    """
    name = 'albania_monitor'
    source_timezone = 'Europe/Tirane'
    
    country_code = 'ALB'
    country = '阿尔巴尼亚'
    
    allowed_domains = ['monitor.al']
    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1,
    }

    use_curl_cffi = True

    async def start(self):
        for url in ['https://monitor.al/ekonomi/']:
            yield scrapy.Request(url, callback=self.parse, dont_filter=True)
    
    # CSS selector for the main content area
    fallback_content_selector = ".standard-content, .jeg_main_content, article"

    def parse(self, response):
        """Parses the news list page."""
        # Target both hero and standard article links
        article_nodes = response.css('h3 a.d-block, h2 a.d-block, .jeg_thumb a')
        self.logger.info(f"Found {len(article_nodes)} article links on {response.url}")

        has_valid_item_in_window = False
        
        # Track seen URLs in this page to avoid processing the same hero article twice
        page_seen_urls = set()

        for link in article_nodes:
            href = link.attrib.get('href')
            if not href or href in page_seen_urls:
                continue
            url = response.urljoin(href)
            page_seen_urls.add(href)

            # Improved date extraction with fallback for hero articles
            card_root = link.xpath("./ancestor::*[self::article or self::div[contains(@class,'jeg_post') or contains(@class,'post')] or self::div[contains(@class,'jeg_hero')]][1]")
            
            # Try multiple common JNews date selectors
            date_str = card_root.css('.jeg_meta_date::text, .jeg_post_meta .jeg_meta_date::text, .jeg_post_date::text').get()
            
            publish_time = None
            if date_str:
                # Clean suffixes like " / 13 Min Lexim"
                date_str = re.split(r'[/\s\d]+Min Lexim', date_str)[0].strip()
                dt_local = dateparser.parse(date_str, languages=['sq', 'en'])
                publish_time = self.parse_to_utc(dt_local)

            # Core logic: Should we process this article?
            is_valid = self.should_process(url, publish_time)
            
            if not is_valid:
                continue
            
            # CRITICAL: Only allow pagination if we have a CONFIRMED recent date
            # This prevents infinite pagination when dates fail to parse
            if publish_time and publish_time >= self.cutoff_date:
                has_valid_item_in_window = True
            elif publish_time is None and not self.is_already_scraped(url):
                # If date is unknown but it's a new URL, we still crawl it but don't use it to trigger next page
                pass
            
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                dont_filter=self.full_scan,
                meta={"publish_time_hint": publish_time}
            )

        # Pagination: If we found valid items or dates were unknown, try the next page
        next_page = response.css('.pagination li.next a::attr(href)').get()
        if next_page and has_valid_item_in_window:
            yield response.follow(next_page, callback=self.parse, dont_filter=True)

    def parse_detail(self, response):
        """
        Standardized detail parsing using the base class helper.
        """
        yield self.auto_parse_item(response)

