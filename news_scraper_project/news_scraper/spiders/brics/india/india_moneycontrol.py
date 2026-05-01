import scrapy
import re
import json
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class IndiaMoneycontrolSpider(SmartSpider):
    name = "india_moneycontrol"
    country_code = 'IND'
    country = '印度'
    language = 'en'
    allowed_domains = ["moneycontrol.com"]
    target_table = "ind_moneycontrol"
    
    source_timezone = 'Asia/Kolkata'
    use_curl_cffi = True
    
    # Sitemap based spider currently doesn't parse lastmod, 
    # so we disable strict mode to avoid skipping all URLs.
    strict_date_required = False
    
    fallback_content_selector = "#contentdata, .page_left_wrapper, .content_wrapper, .article_desc"

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            # Minimal GDPR consent cookies to bypass /europe/ redirect.
            # These are static preference markers, not session tokens — they don't expire.
            "Cookie": "gdpr_region=ca; gdpr_userpolicy_eu=1; _w18g_consent_ca=Y; _w18g_gdpr_consent_data_ca=personal_info_consent:Y#personalization_consent:Y#age_consent:Y#recommendation_adv_remarketting_consent:Y#adv_remarketting_consent:Y#marketting_communication_consent:Y"
        },
    }

    async def start(self):
        # Modernized API: async start() replaces start_requests()
        headers = self.custom_settings.get("DEFAULT_REQUEST_HEADERS", {})
        yield scrapy.Request(
            url="https://www.moneycontrol.com/news/business/economy/page-1/",
            callback=self.parse_list,
            headers=headers,
            meta={'current_page': 1},
            dont_filter=True
        )

    def parse_list(self, response):
        current_page = response.meta.get('current_page', 1)
        # Extract links from the economy news list
        links = response.css('.fleft a::attr(href), #left-container a::attr(href), .article_title a::attr(href)').getall()
        
        # If no links found, check if it's because of the GDPR redirect
        if not links:
            if b'/europe/' in response.body or b'gdpr' in response.body.lower():
                self.logger.error(f"GDPR Redirect detected on page {current_page}. Cookies might have failed.")
            else:
                self.logger.warning(f"No links found on page {current_page}. Might be the end of the list.")
            return

        new_links_found = 0
        valid_article_links = set()

        for link in set(links):
            # STRICT FILTERING: 
            # 1. Must be an economy link
            # 2. Must be an ACTUAL ARTICLE (ends in .html)
            # 3. Must NOT be a pagination link (contains /page-)
            if '/news/business/economy/' in link:
                if link.endswith('.html') and '/page-' not in link:
                    valid_article_links.add(response.urljoin(link))

        for full_url in valid_article_links:
            if self.should_process(full_url, None):
                new_links_found += 1
                yield scrapy.Request(
                    full_url, 
                    callback=self.parse_detail,
                    headers=self.custom_settings.get("DEFAULT_REQUEST_HEADERS", {})
                )
        
        # Logic: If we found new valid articles on this page, or we are in full_scan mode,
        # we proceed to the next page.
        if (new_links_found > 0) or (self.full_scan and valid_article_links):
            next_page = current_page + 1
            next_url = f"https://www.moneycontrol.com/news/business/economy/page-{next_page}/"
            self.logger.info(f"Continuing to page {next_page}...")
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_list,
                headers=self.custom_settings.get("DEFAULT_REQUEST_HEADERS", {}),
                meta={'current_page': next_page},
                priority=-next_page,
                dont_filter=True
            )
        else:
            reason = "No new articles found" if not new_links_found else "Reached end of list"
            self.logger.info(f"Stopping at page {current_page}: {reason}")

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class, 'article_title')]/text() | //meta[@property='og:title']/@content",
            publish_time_xpath="//meta[@property='og:article:published_time']/@content | //meta[@property='article:published_time']/@content"
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

        item['author'] = response.css('.article_author::text, .article_author span::text').get() or "Moneycontrol Staff"
        item['country_code'] = self.country_code
        item['country'] = self.country
        
        yield item
