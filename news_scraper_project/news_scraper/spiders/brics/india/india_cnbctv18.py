import scrapy
import re
import json
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class IndiaCnbctv18Spider(SmartSpider):
    name = 'india_cnbctv18'
    country_code = 'IND'
    country = '印度'
    language = 'en'
    allowed_domains = ['cnbctv18.com']
    target_table = "ind_cnbctv18"
    
    source_timezone = 'Asia/Kolkata'
    use_curl_cffi = True
    
    fallback_content_selector = ".articleWrap, .narticle-data, .article-content, #main-content"

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def start_requests(self):
        # Categories from user's network capture
        categories = [
            "technology", "economy", "auto",
        ]
        
        for cat in categories:
            # We start with offset 0 and fetch 20 items per request for efficiency
            url = self.build_api_url(cat, offset=0)
            yield scrapy.Request(
                url, 
                callback=self.parse_api, 
                meta={'category': cat, 'offset': 0},
                dont_filter=True
            )

    def build_api_url(self, category, offset=0, count=20):
        # Original pattern provided by user
        fields = "story_id,display_headline,weburl_r,images,timetoread,created_at,updated_at"
        filter_json = json.dumps({"categories.slug": category})
        return (f"https://api-en.cnbctv18.com/nodeapi/v1/cne/get-article-list?"
                f"count={count}&offset={offset}&fields={fields}&filter={filter_json}&"
                f"sortOrder=desc&sortBy=created_at")

    def parse_api(self, response):
        try:
            res = json.loads(response.text)
            if not res.get('status') or not res.get('data'):
                return
        except Exception as e:
            self.logger.error(f"Failed to parse API JSON: {e}")
            return

        category = response.meta['category']
        offset = response.meta['offset']
        
        has_valid_item_in_window = False
        
        for entry in res['data']:
            rel_url = entry.get('weburl_r')
            if not rel_url:
                continue
            
            # Explicitly join with the main domain, not the API domain
            url = f"https://www.cnbctv18.com{rel_url}"
            
            # Date handling: "2026-04-29 18:39:37" (Assuming IST)
            created_at = entry.get('created_at')
            publish_time = None
            if created_at:
                try:
                    # SmartSpider.parse_to_utc handles string parsing + tz conversion
                    publish_time = self.parse_to_utc(created_at)
                except:
                    pass

            if self.should_process(url, publish_time):
                has_valid_item_in_window = True
                yield scrapy.Request(
                    url, 
                    callback=self.parse_detail, 
                    meta={'publish_time_hint': publish_time}
                )

        # Pagination
        if has_valid_item_in_window:
            new_offset = offset + 20
            # Safety limit to avoid infinite loops on very large categories
            if new_offset < 200: 
                next_url = self.build_api_url(category, offset=new_offset)
                yield scrapy.Request(
                    next_url, 
                    callback=self.parse_api, 
                    meta={'category': category, 'offset': new_offset}
                )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text() | //meta[@property='og:title']/@content",
            publish_time_xpath="//meta[@property='article:published_time']/@content"
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

        item['author'] = response.css('.author-name::text, .byline-author::text').get() or "CNBCTV18 Staff"
        item['country_code'] = self.country_code
        item['country'] = self.country
        
        yield item
