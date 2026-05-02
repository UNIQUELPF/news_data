import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class IranIranIntlSpider(SmartSpider):
    name = 'iran_iranintl'
    source_timezone = 'UTC'
    # DO NOT set fallback_content_selector = "article" here.
    # This site uses Next.js streaming. Narrowing down to <article> in raw HTML
    # only sees skeletons. Removing the selector allows Trafilatura to find
    # the full content in the page source.
    fallback_content_selector = None
    
    country_code = 'IRN'
    country = '伊朗'
    language = 'en'
    
    allowed_domains = ['iranintl.com']
    
    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    use_curl_cffi = True

    async def start(self):
        # Economy and environment section
        yield scrapy.Request('https://www.iranintl.com/en/economy-and-environment', callback=self.parse, dont_filter=True)

    def parse(self, response):
        # Extract article links matching /en/YYYYMMDDNNNN
        # Based on the sample: /en/202604301708
        articles = response.xpath("//a[contains(@href, '/en/20')]")
        self.logger.info(f"Found {len(articles)} potential articles on {response.url}")

        has_valid_item_in_window = False
        for article in articles:
            url = response.urljoin(article.xpath("@href").get())
            
            # Extract date from URL: /en/202604301708 -> 2026-04-30
            date_match = re.search(r'/en/(\d{4})(\d{2})(\d{2})', url)
            publish_time = None
            if date_match:
                try:
                    year, month, day = map(int, date_match.groups())
                    publish_time = datetime(year, month, day)
                    publish_time = self.parse_to_utc(publish_time)
                except ValueError:
                    pass
            
            if not self.should_process(url, publish_time):
                if publish_time and publish_time < self.cutoff_date:
                    self.logger.info(f"Hit date boundary at {publish_time}. Stopping pagination.")
                    has_valid_item_in_window = False
                    break
                continue
                
            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                dont_filter=self.full_scan,
                meta={'publish_time_hint': publish_time}
            )

        if has_valid_item_in_window:
            # Pagination: https://www.iranintl.com/en/economy-and-environment?page=2
            current_page = self._get_page_num(response.url)
            next_page = current_page + 1
            next_page_url = f"https://www.iranintl.com/en/economy-and-environment?page={next_page}"
            yield scrapy.Request(next_page_url, callback=self.parse, dont_filter=True)

    def _get_page_num(self, url):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        try:
            return int(params.get('page', [1])[0])
        except:
            return 1

    def parse_detail(self, response):
        # Standard auto-parsing
        item = self.auto_parse_item(
            response,
            title_xpath="//meta[@property='og:title']/@content | //h1/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        
        # Prioritize og:image
        og_image = response.xpath("//meta[@property='og:image']/@content").get()
        if og_image:
            if 'images' not in item or not item['images']:
                item['images'] = [og_image]
            elif og_image not in item['images']:
                item['images'].insert(0, og_image)
        
        # Clean images
        if 'images' in item and item['images']:
            item['images'] = [img if isinstance(img, str) else img.get('url') for img in item['images'] if img]

        item['section'] = 'Economy'
        
        yield item
