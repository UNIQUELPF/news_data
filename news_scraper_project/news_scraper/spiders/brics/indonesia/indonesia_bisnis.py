import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class IndonesiaBisnisSpider(SmartSpider):
    name = "indonesia_bisnis"
    country_code = 'IDN'
    country = '印度尼西亚'
    language = 'id'
    allowed_domains = ["bisnis.com", "ekonomi.bisnis.com"]
    target_table = "idn_bisnis"
    
    # Jakarta Timezone (WIB)
    source_timezone = 'Asia/Jakarta'
    use_curl_cffi = True
    
    fallback_content_selector = ".detailsContent, .detailsDescription, article"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        # Category 43 is Economy
        yield scrapy.Request(
            url="https://www.bisnis.com/index?categoryId=43&page=1",
            callback=self.parse_list,
            meta={'current_page': 1},
            dont_filter=True
        )

    def parse_list(self, response):
        current_page = response.meta.get('current_page', 1)
        # Extract links from the index
        links = response.css('a.artLink::attr(href)').getall()
        
        new_links_found = 0
        valid_article_links = []

        for link in set(links):
            if '/read/' in link:
                full_url = response.urljoin(link)
                # Bisnis.com URL pattern: /read/YYYYMMDD/
                publish_time_hint = self._extract_date_from_url(full_url)
                
                # CRITICAL: Early stop if date is behind cutoff
                if publish_time_hint and not self.full_scan:
                    # Use date objects for clean, timezone-independent comparison
                    hint_date = publish_time_hint.date()
                    cutoff_date = self.cutoff_date.date()
                    
                    if hint_date < cutoff_date:
                        self.logger.info(f"STOPPING: Article date {hint_date} is older than cutoff {cutoff_date}. URL: {full_url}")
                        continue 

                if self.should_process(full_url, publish_time_hint):
                    valid_article_links.append((full_url, publish_time_hint))

        for full_url, time_hint in valid_article_links:
            new_links_found += 1
            yield scrapy.Request(
                full_url, 
                callback=self.parse_detail,
                meta={'publish_time_hint': time_hint}
            )
        
        # Stop pagination if:
        # 1. We didn't find any new links (incremental sync complete)
        # 2. OR we encountered an article older than cutoff (time-based sync complete)
        # 3. BUT if full_scan is on, keep going until no more links
        should_continue = (new_links_found > 0)
        if self.full_scan and valid_article_links:
            should_continue = True
            
        if should_continue and current_page < 100:
            next_page = current_page + 1
            next_url = f"https://www.bisnis.com/index?categoryId=43&page={next_page}"
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_list,
                meta={'current_page': next_page},
                priority=-next_page,
                dont_filter=True
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class, 'detailsTitleCaption')]/text() | //meta[@property='og:title']/@content",
            publish_time_xpath="//div[contains(@class, 'detailsAttributeDates')]/text() | //meta[@property='og:updated_time']/@content"
        )

        # Metadata refinement
        item['author'] = response.css(".detailsAttributeAuthor a::text, .detailsAuthor a::text").get() or "Bisnis.com"
        item['section'] = "Economy"
        
        # Explicitly extract cover image (Bisnis.com specific)
        cover_image = response.css(".detailsCover img::attr(src), .detailsCover img::attr(data-src)").get()
        if cover_image:
            full_cover_url = response.urljoin(cover_image)
            if not item.get('images'):
                item['images'] = []
            if full_cover_url not in item['images']:
                item['images'].insert(0, full_cover_url)

        # Final safety check on publish_time (V2 requirement)
        if not self.full_scan and item.get('publish_time'):
            if item['publish_time'] < self.cutoff_date:
                return

        yield item

    def _extract_date_from_url(self, url):
        """Helper to extract date from Bisnis.com URL structure: /read/YYYYMMDD/"""
        match = re.search(r"/read/(\d{4})(\d{2})(\d{2})/", url)
        if match:
            year, month, day = map(int, match.groups())
            try:
                dt = datetime(year, month, day)
                return self.parse_to_utc(dt)
            except Exception:
                pass
        return None
