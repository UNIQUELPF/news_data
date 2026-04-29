import scrapy
import re
from datetime import datetime
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from news_scraper.spiders.smart_spider import SmartSpider

class EthiopiaReporterSpider(SmartSpider):
    name = "ethiopia_reporter"
    country_code = 'ETH'
    country = '埃塞俄比亚'
    allowed_domains = ["thereporterethiopia.com"]
    target_table = "ethi_reporter"
    
    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors'
        }
    }
    
    # API endpoints
    base_api_url = 'https://www.thereporterethiopia.com/wp-json/wp/v2/posts?categories=1960&_embed=1&per_page=50&page={}'

    def start_requests(self):
        url = self.base_api_url.format(1)
        yield scrapy.Request(url, callback=self.parse_api, dont_filter=True, meta={'page': 1})

    def parse_api(self, response):
        try:
            data = response.json()
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
            return

        if not data or not isinstance(data, list):
            self.logger.info("End of API data reached.")
            return

        has_valid_item_in_window = False
        for post in data:
            url = post.get('link')
            date_str = post.get('date_gmt') or post.get('date')
            
            publish_time = None
            if date_str:
                try:
                    publish_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    pass
            
            publish_time_utc = self.parse_to_utc(publish_time) if publish_time else None

            if self.should_process(url, publish_time_utc):
                has_valid_item_in_window = True
                
                # Extract content from JSON instead of making a new request
                title_raw = post.get('title', {}).get('rendered', '')
                title = BeautifulSoup(title_raw, "html.parser").get_text().strip()
                
                content_html = post.get('content', {}).get('rendered', '')
                soup = BeautifulSoup(content_html, "html.parser")
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                content_plain = soup.get_text(separator=' ', strip=True)
                
                author = "Reporter Staff"
                author_list = post.get('_embedded', {}).get('author', [])
                if author_list:
                    author = author_list[0].get('name', author)

                item = {
                    'url': url,
                    'title': title,
                    'publish_time': publish_time_utc,
                    'author': author,
                    'content_plain': content_plain,
                    'content_markdown': md(content_html) if content_html else content_plain,
                    'section': 'News',
                    'country_code': self.country_code,
                    'country': self.country
                }
                
                # Dynamic language detection
                text_for_lang = title + content_plain
                if re.search(r"[\u1200-\u137F]", text_for_lang):
                    item['language'] = 'am'
                else:
                    item['language'] = 'en'
                
                # Standard V2 image extraction
                featured_media = post.get('_embedded', {}).get('wp:featuredmedia', [])
                if featured_media:
                    item['featured_image'] = featured_media[0].get('source_url')
                    item['images'] = [item['featured_image']] if item['featured_image'] else []
                
                yield item

        if has_valid_item_in_window:
            page = response.meta.get('page', 1)
            if page < 100:
                next_page = page + 1
                yield scrapy.Request(
                    url=self.base_api_url.format(next_page),
                    callback=self.parse_api,
                    meta={'page': next_page},
                    dont_filter=True
                )
