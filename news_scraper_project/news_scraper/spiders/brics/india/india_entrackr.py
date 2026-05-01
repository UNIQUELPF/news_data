import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class IndiaEntrackrSpider(SmartSpider):
    name = 'india_entrackr'
    country_code = 'IND'
    country = '印度'
    language = 'en'
    allowed_domains = ['entrackr.com']
    target_table = 'ind_entrackr'
    
    source_timezone = 'Asia/Kolkata'
    use_curl_cffi = True
    
    fallback_content_selector = ".content-wrapper, .post-content, .article-content, .entry-content"

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def start_requests(self):
        url = 'https://entrackr.com/news'
        yield scrapy.Request(url, callback=self.parse_list, dont_filter=True, meta={'page': 1})

    def parse_list(self, response):
        # IMPORTANT: Only select articles from the main content area.
        # This excludes the "Latest Stories" sidebar which would otherwise keep the 
        # pagination alive forever with recent dates.
        articles = response.css('main .article-box, main .small-post, #feat-len-1')
        if not articles:
            # Fallback if 'main' tag is missing or structured differently
            articles = response.css('.article-box, .small-post')
        
        has_valid_item_in_window = False
        for article in articles:
            link = article.css('a::attr(href)').get()
            if not link:
                continue
            url = response.urljoin(link)
            
            # Robust date extraction from list page
            # Try multiple ways to get the text to avoid None values
            date_nodes = article.css('.publish-date *::text').getall()
            date_str = " ".join([d.strip() for d in date_nodes if d.strip()])
            
            publish_time = None
            if date_str:
                try:
                    # Clean whitespace and parse
                    parsed = dateparser.parse(date_str)
                    if parsed:
                        publish_time = self.parse_to_utc(parsed)
                        self.logger.debug(f"Parsed list date for {url}: {publish_time}")
                except Exception as e:
                    self.logger.debug(f"Failed to parse list date {date_str}: {e}")
            else:
                self.logger.warning(f"No date found on list page for {url}")

            # Now we have a date, so should_process can correctly filter
            if self.should_process(url, publish_time):
                has_valid_item_in_window = True
                yield scrapy.Request(
                    url, 
                    callback=self.parse_detail,
                    meta={'publish_time_hint': publish_time}
                )

        # Pagination: follow the 'Next' link ONLY if we found valid items on this page
        if has_valid_item_in_window:
            next_link = response.xpath("//a[contains(text(), 'Next')]/@href").get()
            if next_link:
                next_url = response.urljoin(next_link)
                yield scrapy.Request(next_url, callback=self.parse_list)
            else:
                self.logger.info("No more pages found (Next button missing).")
        else:
            self.logger.info("Reached the end of the date window. Stopping pagination.")

    def parse_detail(self, response):
        # 1. Manually extract the specific date string from JSON-LD to avoid passing long blocks
        json_time = response.xpath("//script[@type='application/ld+json']/text()").re_first(r'"datePublished":\s*"([^"]+)"')
        
        # 2. Use a specific XPath to avoid picking up dates from sidebars or related posts
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//div[contains(@class, 'author-detail')]//time/text()"
        )
        
        # 3. If the high-precision JSON-LD time was found, use it to override
        if json_time:
            try:
                parsed_time = dateparser.parse(json_time)
                if parsed_time:
                    item['publish_time'] = self.parse_to_utc(parsed_time)
            except:
                pass
        
        # Priority og:image
        og_image = response.xpath("//meta[@property='og:image']/@content").get()
        if og_image:
            if not item.get('images'):
                item['images'] = []
            if og_image not in item['images']:
                item['images'].insert(0, og_image)

        # Stop if older than cutoff or absolute floor
        if not self.full_scan and item['publish_time']:
            if item['publish_time'] < self.cutoff_date:
                return
            if item['publish_time'] < self.earliest_date:
                return

        item['author'] = response.css('.author-name::text, [rel="author"]::text').get() or "Entrackr Staff"
        item['country_code'] = self.country_code
        item['country'] = self.country
        
        yield item
