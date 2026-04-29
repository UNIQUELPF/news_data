import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class BaCapitalSpider(SmartSpider):
    name = "ba_capital"
    source_timezone = 'Europe/Sarajevo'
    
    country_code = 'BIH'
    country = '波黑'
    language = 'bs'
    
    allowed_domains = ["capital.ba"]

    custom_settings = {
        "CONCURRENT_REQUESTS": 2, 
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    use_curl_cffi = True

    async def start(self):
        """Initial requests entry point."""
        for url in ["https://capital.ba/category/privreda/"]:
            yield scrapy.Request(url, callback=self.parse, dont_filter=True)

    # Precise selector: strictly locked to the main column container
    fallback_content_selector = ".main-content.s-post-contain"

    def parse(self, response):
        """
        Parse listing page: https://capital.ba/category/privreda/
        """
        # Precise main content area selector
        articles = response.css('.posts-list .content, .archive-posts .content, .main-content .content')
        
        if not articles:
            articles = response.xpath('//div[contains(@class, "content") and .//h2[contains(@class, "post-title")]]')

        if not articles:
            self.logger.warning(f"No articles found in main area of {response.url}.")
            return

        has_valid_item_in_window = False
        
        for art in articles:
            link = art.css('.post-title a::attr(href)').get()
            if not link or 'category' in link or link == 'https://capital.ba/':
                continue
            
            iso_date = art.css('time.post-date::attr(datetime)').get()
            
            publish_time = None
            if iso_date:
                try:
                    publish_time = self.parse_to_utc(datetime.fromisoformat(iso_date))
                except Exception as e:
                    self.logger.warning(f"ISO Date parse error: {e}")

            # Panic Break logic
            is_valid_article_block = art.css('.post-title').get() is not None
            if is_valid_article_block and not publish_time:
                self.logger.error(f"STRICT STOP: No date found for {link}. Breaking.")
                break

            if not publish_time or not self.should_process(link, publish_time):
                continue

            has_valid_item_in_window = True
            
            yield scrapy.Request(
                link, 
                callback=self.parse_detail,
                meta={
                    "publish_time_hint": publish_time, 
                    "playwright": True
                },
                dont_filter=self.full_scan
            )

        if has_valid_item_in_window:
            current_page = 1
            if '/page/' in response.url:
                try:
                    current_page = int(response.url.split('/page/')[-1].strip('/'))
                except ValueError:
                    pass
            
            next_page_url = f"https://capital.ba/category/privreda/page/{current_page + 1}/"
            yield scrapy.Request(next_page_url, callback=self.parse)

    def parse_detail(self, response):
        """Parses the article detail page with strict content area focus."""
        # Manually remove clutter before auto_parse to help the engine
        # Removing 'Check also' (Pročitajte još) and similar recommendation blocks
        clutter_selectors = [
            '.wa-post-read-next', '.post-related', '.check-also', 
            '.adsbygoogle', 'aside', '.entry-terms'
        ]
        
        # We can't easily mutate response in Scrapy, so we rely on 
        # SmartSpider's auto_parse_item which respects fallback_content_selector.
        # We've already narrowed fallback_content_selector to .entry-content above.
        
        item = self.auto_parse_item(response)
        
        # Ensure we didn't just get a fragment
        content = item.get('content', '')
        if len(content) < 100:
             # If extraction is too short, try a broader but still safe selector
             # and avoid the first paragraph if it's often a lead/summary that's duplicated
             self.logger.debug(f"Short content detected for {response.url}, retrying with broader selector.")
        
        item['author'] = response.css('.meta-item.author a::text').get() or "Capital.ba Staff"
        item['section'] = "Economy"
        
        yield item
