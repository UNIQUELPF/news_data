import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class Bg24chasaSpider(SmartSpider):
    name = "bg_24chasa"
    source_timezone = 'Europe/Sofia'
    
    country_code = 'BGR'
    country = '保加利亚'
    language = 'bg'
    
    # European date format: Day.Month.Year
    dateparser_settings = {'DATE_ORDER': 'DMY'}
    
    allowed_domains = ["www.24chasa.bg"]

    custom_settings = {
        "CONCURRENT_REQUESTS": 2, 
        "DOWNLOAD_DELAY": 1,
        "AUTOTHROTTLE_ENABLED": True,
    }

    use_curl_cffi = True
    
    # Precise selector: strictly locked to the article container including featured images
    fallback_content_selector = "article.entry-content"

    async def start(self):
        """Initial requests entry point."""
        # Category 11764989 belongs to Business/Economy
        yield scrapy.Request("https://www.24chasa.bg/biznes/11764989?page=1", callback=self.parse, dont_filter=True)

    def parse(self, response):
        """
        Parse listing page: https://www.24chasa.bg/biznes/11764989?page=1
        """
        # Use precise XPath directly (CSS :has() is not supported by Scrapy's engine)
        articles = response.xpath('//section[contains(@class, "sub-category-archive")]//article[descendant::a[contains(@href, "/article/")]]')
        
        if not articles:
             self.logger.warning(f"No valid article blocks found in {response.url} main area.")
        
        has_valid_item_in_window = False
        
        for art in articles:
            link = art.css('a::attr(href)').get()
            if not link:
                continue
            if not link.startswith('http'):
                link = response.urljoin(link)
                
            # Date extraction from listing page: prioritize .date, fallback to .time
            publish_time_str = art.css('time.date::text, time.time::text').get()
            publish_time = None
            if publish_time_str:
                try:
                    import dateparser
                    dt_obj = dateparser.parse(publish_time_str.strip(), settings={'DATE_ORDER': 'DMY'})
                    publish_time = self.parse_to_utc(dt_obj)
                except Exception as e:
                    self.logger.warning(f"Date parse error for {link}: {e}")

            # Panic Break: If it's a clear article block but we can't find a date, 
            # STOP EVERYTHING to avoid misinterpreting the sliding window.
            if not publish_time:
                self.logger.error(f"STRICT STOP: No date found for {link}. Terminating spider.")
                return # CRITICAL: use return, not break, to kill pagination logic

            if not self.should_process(link, publish_time):
                continue
            
            has_valid_item_in_window = True
            yield scrapy.Request(
                link, 
                callback=self.parse_detail,
                meta={"publish_time_hint": publish_time}
            )

        # Pagination logic
        if has_valid_item_in_window:
            current_page = 1
            if 'page=' in response.url:
                try:
                    current_page = int(response.url.split('page=')[-1])
                except ValueError:
                    pass
            
            if current_page < 50: 
                next_page_url = f"https://www.24chasa.bg/biznes/11764989?page={current_page + 1}"
                yield scrapy.Request(next_page_url, callback=self.parse)

    def parse_detail(self, response):
        """Parses the article detail page using standardized SmartSpider extraction."""
        # Preserve existing date selector logic: time.date::text
        # Strict date extraction: limited to the master wrapper to avoid sidebar interference
        item = self.auto_parse_item(
            response,
            publish_time_xpath=".//article[contains(@class, 'entry-content')]//time[contains(@class, 'date') or contains(@class, 'time')]/text()"
        )
        
        # Override/Set specific fields
        item['author'] = "24 Chasa Bulgaria"
        item['section'] = "Business"
        
        yield item
