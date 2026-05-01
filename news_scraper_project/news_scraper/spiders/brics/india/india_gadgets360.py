import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class IndiaGadgets360Spider(SmartSpider):
    name = 'india_gadgets360'
    country_code = 'IND'
    country = '印度'
    language = 'en'
    allowed_domains = ['gadgets360.com']
    target_table = "ind_gadgets360"
    
    source_timezone = 'Asia/Kolkata'
    use_curl_cffi = True
    
    fallback_content_selector = ".content_text, #article_content, .story_content, .ins_storybody"

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        # Using the AJAX endpoint for cleaner data and more reliable pagination
        base_urls = [
            "https://www.gadgets360.com/news",
        ]
        for base_url in base_urls:
            ajax_url = f"{base_url}?pagesize=20&page=1&content_type=news&isAjax=1"
            yield scrapy.Request(
                ajax_url, 
                callback=self.parse_list, 
                dont_filter=True, 
                meta={'page': 1, 'base_url': base_url},
                headers={'X-Requested-With': 'XMLHttpRequest'}
            )

    def parse_list(self, response):
        # The AJAX endpoint returns HTML fragments (wrapped in <ul><li>)
        items = response.css('li')
        if not items:
            self.logger.warning(f"No AJAX items found on {response.url}.")
            return

        has_valid_item_in_window = False
        for item in items:
            # Link and date extraction remains the same as they are part of the fragment
            url_node = item.css('.caption_box a::attr(href)').get()
            date_text = item.css('.dateline::text').get()
            
            if not url_node:
                continue
                
            url = response.urljoin(url_node)
            
            # Clean date_text: "Written by ..., 29 April 2026"
            clean_date = None
            if date_text and ',' in date_text:
                clean_date = date_text.split(',')[-1].strip()
            
            publish_time = self.parse_date(clean_date) if clean_date else None
            
            if self.should_process(url, publish_time):
                has_valid_item_in_window = True
                yield scrapy.Request(url, callback=self.parse_detail, meta={'publish_time_hint': publish_time})

        # Pagination: Increment the 'page' parameter
        if has_valid_item_in_window:
            page = response.meta.get('page', 1)
            next_page = page + 1
            base_url = response.meta.get('base_url')
            next_url = f"{base_url}?pagesize=20&page={next_page}&content_type=news&isAjax=1"
            yield scrapy.Request(
                next_url, 
                callback=self.parse_list, 
                meta={'page': next_page, 'base_url': base_url},
                headers={'X-Requested-With': 'XMLHttpRequest'}
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//div[contains(@class,'story_container')]//h1/text() | //meta[@property='og:title']/@content",
            publish_time_xpath="//meta[@itemprop='datePublished']/@content | //meta[@property='article:published_time']/@content"
        )
        
        # Priority og:image
        og_image = response.xpath("//meta[@property='og:image']/@content").get()
        if og_image:
            if not item.get('images'):
                item['images'] = []
            if og_image not in item['images']:
                item['images'].insert(0, og_image)

        # Stop if older than cutoff
        if not self.full_scan and item['publish_time'] and item['publish_time'] < self.cutoff_date:
            return

        item['author'] = response.css('.author_name a::text, .byline a::text').get() or "Gadgets360 Staff"
        item['country_code'] = self.country_code
        item['country'] = self.country
        
        yield item
