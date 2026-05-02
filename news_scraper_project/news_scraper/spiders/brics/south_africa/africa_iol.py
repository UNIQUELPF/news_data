import json
import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class AfricaIolSpider(SmartSpider):
    """
    South Africa IOL spider.
    Modernized V2: Uses the IOL API for efficient discovery and ContentEngine for extraction.
    """
    name = 'africa_iol'
    country_code = 'ZAF'
    country = '南非'
    language = 'en'
    source_timezone = 'Africa/Johannesburg'
    use_curl_cffi = True
    fallback_content_selector = '[class*="article_content"]'
    allowed_domains = ['iol.co.za']

    custom_settings = {
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 500,
        }
    }

    def start_requests(self):
        yield self.make_api_request(page=1)

    def make_api_request(self, page):
        # We target business/economy specifically as per the original spider
        url = f"https://iol.co.za/api-proxy/apiv1/pub/articles/get-all/?exclude_fields=widgets,images,blur&limit=100&publication=iol&section=business&subsection=economy&page={page}"
        headers = {
            "consumer-key": "759d7cf855545a3177a2ca5ecbebbc83b74b5cb8",
            "referer": "https://iol.co.za/business/economy/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"
        }
        return scrapy.Request(
            url,
            headers=headers,
            callback=self.parse_api,
            meta={'page': page},
            dont_filter=True
        )

    def parse_api(self, response):
        try:
            data = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON on {response.url}: {e}")
            return

        if not data:
            self.logger.info("Empty data from API. Stopping pagination.")
            return

        has_valid_item_in_window = False
        for item in data:
            pub_url = item.get('pub_url')
            if not pub_url:
                continue
                
            url = "https://www.iol.co.za" + pub_url if not pub_url.startswith('http') else pub_url
            
            # Date extraction logic (handles ms, s, and strings)
            pub_val = item.get('published')
            publish_time = None
            if isinstance(pub_val, dict) and '$date' in pub_val:
                try:
                    publish_time = self.parse_to_utc(datetime.fromtimestamp(int(pub_val['$date']) / 1000.0))
                except Exception: pass
            elif isinstance(pub_val, (int, float)):
                try:
                    if pub_val > 253402300799: # ms
                        publish_time = self.parse_to_utc(datetime.fromtimestamp(pub_val / 1000.0))
                    else: # s
                        publish_time = self.parse_to_utc(datetime.fromtimestamp(pub_val))
                except Exception: pass
            elif isinstance(pub_val, str):
                publish_time = self.parse_date(pub_val)

            if not self.should_process(url, publish_time):
                # Stop pagination if we hit old content in the API stream
                if publish_time and publish_time < self.cutoff_date:
                    self.logger.info(f"Hit date boundary at {publish_time}. Stopping pagination.")
                    has_valid_item_in_window = False
                    break
                continue

            has_valid_item_in_window = True

            # Metadata from API
            title = item.get('title', 'Untitled')
            authors = item.get('authors', [])
            author_names = [a.get('name') for a in authors if isinstance(a, dict) and a.get('name')]
            author = ', '.join(author_names) if author_names else None
            
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    'publish_time_hint': publish_time,
                    'title_hint': title,
                    'author_hint': author
                }
            )

        if has_valid_item_in_window:
            next_page = response.meta['page'] + 1
            yield self.make_api_request(next_page)

    def parse_detail(self, response):
        # Merge API hints with detail page content via auto_parse_item
        item = self.auto_parse_item(response)
        
        # Manual image fallback (IOL's widget-based layout can confuse trafilatura)
        if not item.get('images'):
            # Priority: 1. Picture tag (main article image), 2. OG Image meta
            main_image = response.css("picture img::attr(src)").get() or \
                         response.xpath("//meta[@property='og:image']/@content").get()
            if main_image:
                item['images'] = [response.urljoin(main_image)]
        
        if not item.get('author') and response.meta.get('author_hint'):
            item['author'] = response.meta['author_hint']
            
        yield item
