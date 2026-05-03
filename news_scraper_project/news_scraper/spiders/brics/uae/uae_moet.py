# 阿联酋moet爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from datetime import datetime
import re

class UaeMoetSpider(SmartSpider):
    name = "uae_moet"

    country_code = 'ARE'
    country = '阿联酋'
    language = 'en'
    source_timezone = 'Asia/Dubai'
    use_curl_cffi = True
    
    # Selective selectors for Ministry of Economy
    fallback_content_selector = ".news_detail, .content_area, [class*='content-spacious']"
    
    allowed_domains = ["moet.gov.ae"]

    custom_settings = {
        'DOWNLOAD_DELAY':1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 500,
        }
    }

    async def start(self):
        url = "https://www.moet.gov.ae/en/news"
        yield scrapy.Request(url, callback=self.parse_list, meta={'page': 1}, dont_filter=True)

    def parse_list(self, response):
        # Implementation based on existing logic but modernized
        cards = response.css('div.item.custom_animation')
        if not cards:
            return

        has_valid_item_in_window = False
        
        for card in cards:
            link = card.css('a[href*="/en/-/"]::attr(href)').get()
            if not link:
                continue
                
            url = response.urljoin(link)
            
            # Date extraction from card
            date_nodes = card.xpath('.//div[contains(@class, "date")]//text()').getall()
            date_str = "".join(date_nodes).strip()
            publish_time = self.parse_date(date_str)
            
            # Title extraction from card - using multiple selectors for safety
            title_hint = card.css('div.head_line p::text').get() or card.css('div.head_line ::text').get()
            if title_hint:
                title_hint = title_hint.strip()
            
            # Detailed debug logging for date filtering
            if not publish_time:
                 self.logger.warning(f"Could not parse date for {url} from string '{date_str}'")
            
            if not self.should_process(url, publish_time):
                # We already added a debug log in SmartSpider.should_process
                continue
                
            self.logger.info(f"Processing: {title_hint} ({date_str})")
            has_valid_item_in_window = True
            
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    'publish_time_hint': publish_time,
                    'title_hint': title_hint
                }
            )

        # Pagination using URL template
        if has_valid_item_in_window:
            current_page = response.meta.get('page', 1)
            # Existing template logic
            for a in response.css("ul.pagination a.page-link[href]"):
                href = a.get()
                if "_cur=" in href:
                    next_page = current_page + 1
                    # Extract the base URL and replace _cur=N
                    next_url = re.sub(r'(_cur=)\d+', rf'\g<1>{next_page}', response.url)
                    if "_cur=" not in response.url:
                        next_url = response.url + f"?_cur={next_page}" if "?" not in response.url else response.url + f"&_cur={next_page}"
                    
                    yield scrapy.Request(next_url, callback=self.parse_list, meta={'page': next_page})
                    break

    def parse_detail(self, response):
        # Using specific xpaths to bypass decoy <h1>Navigation</h1> and form-field <div>date</div>.
        # title_hint and publish_time_hint from parse_list will be used if these fail.
        item = self.auto_parse_item(
            response,
            title_xpath="//span[contains(@class, 'asset-title')]//text() | //h1[not(contains(@class, 'hide-accessible'))]//text()",
            publish_time_xpath="//div[contains(@class, 'date') and not(contains(@class, 'hidden'))]//text()"
        )
        
        item['author'] = "Ministry of Economy"
        item['section'] = "News"
        
        yield item
