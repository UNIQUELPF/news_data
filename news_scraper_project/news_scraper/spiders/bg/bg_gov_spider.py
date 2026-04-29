import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class BgGovSpider(SmartSpider):
    name = "bg_gov"
    source_timezone = 'Europe/Sofia'
    
    country_code = 'BGR'
    country = '保加利亚'
    language = 'bg'
    
    allowed_domains = ["www.gov.bg"]

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1,
        "AUTOTHROTTLE_ENABLED": True,
    }

    use_curl_cffi = True
    
    fallback_content_selector = ".view.col-lg-12, .view, article"

    async def start(self):
        """Initial requests entry point."""
        yield scrapy.Request("https://www.gov.bg/bg/prestsentar/novini?page=1", callback=self.parse, dont_filter=True)

    def parse(self, response):
        """
        Parse listing page: https://www.gov.bg/bg/prestsentar/novini?page=1
        """
        # Identify the news items using the actual class from the page
        items = response.css('.item.no-padding')
        
        if not items:
            self.logger.warning(f"No .item.no-padding blocks found in {response.url}. Check selectors.")

        has_valid_item_in_window = False
        for item in items:
            # Preserve the original link pattern as requested
            link = item.css('a[href*="/bg/prestsentar/novini/"]::attr(href)').get()
            if not link or "prestsentar/novini" not in link:
                continue
                
            if not link.startswith('http'):
                link = "https://www.gov.bg" + link

            # Date extraction from .pub-date
            publish_time_str = item.css('.pub-date::text').get()
            publish_time = None
            if publish_time_str:
                try:
                    import dateparser
                    dt_obj = dateparser.parse(publish_time_str.strip(), settings={'DATE_ORDER': 'DMY'})
                    publish_time = self.parse_to_utc(dt_obj)
                except Exception as e:
                    self.logger.warning(f"Date parse error for {link}: {e}")

            # Panic Break: If it's a valid link but we can't find a date, STOP.
            if not publish_time:
                self.logger.error(f"STRICT STOP: No date found for {link}. Terminating spider.")
                return

            # Standard V2 deduplication and incremental check
            if not self.should_process(link, publish_time):
                continue
            
            has_valid_item_in_window = True
            yield scrapy.Request(
                link, 
                callback=self.parse_detail,
                dont_filter=self.full_scan
            )

        # Pagination logic
        if has_valid_item_in_window:
            current_page = 1
            if 'page=' in response.url:
                try:
                    current_page = int(response.url.split('page=')[-1])
                except ValueError:
                    pass
            
            # Rely on the date window logic to decide if we need the next page.
            # No hard page limit; it will stop once has_valid_item_in_window remains False.
            next_page_url = f"https://www.gov.bg/bg/prestsentar/novini?page={current_page + 1}"
            yield scrapy.Request(next_page_url, callback=self.parse, dont_filter=True)

    def parse_detail(self, response):
        """Parses the article detail page using standardized SmartSpider extraction."""
        # Date is often in the first <p> within .view
        item = self.auto_parse_item(
            response,
            publish_time_xpath="//div[contains(@class, 'view')]//p/text()"
        )
        
        # Override/Set specific fields
        item['author'] = "Bulgarian Government"
        item['section'] = "Press Center"
        
        yield item
