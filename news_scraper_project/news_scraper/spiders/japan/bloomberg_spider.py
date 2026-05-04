import scrapy
import json
from urllib.parse import urljoin

from news_scraper.spiders.smart_spider import SmartSpider


class BloombergSpider(SmartSpider):
    name = 'jp_bloomberg'

    country_code = 'JPN'
    country = '日本'
    language = 'en'
    source_timezone = 'Asia/Tokyo'

    allowed_domains = ['bloomberg.com']
    start_urls = ['https://www.bloomberg.com/jp/economics']

    use_curl_cffi = True
    fallback_content_selector = '.body-copy, article'

    # Bloomberg API list endpoints don't expose publish dates on item cards,
    # so we defer date-dependent filtering to the detail page.
    strict_date_required = False

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        },
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_list, dont_filter=True)

    # ------------------------------------------------------------------
    # Listing page – embedded JSON
    # ------------------------------------------------------------------
    def parse_list(self, response):
        """Extract article links from the initialState JSON blob on the listing page."""
        scripts = response.xpath('//script[contains(text(), "initialState")]/text()').getall()

        found_urls = set()
        for script_text in scripts:
            try:
                data = json.loads(script_text)
                self._collect_urls(data, response.url, found_urls)
            except Exception:
                pass

        self.logger.info(
            f"Bloomberg List: Found {len(found_urls)} initial article links from JSON."
        )

        has_valid_item_in_window = False
        for url in found_urls:
            if not self.should_process(url):          # dedup-only (strict_date_required=False)
                continue
            has_valid_item_in_window = True
            yield scrapy.Request(url, callback=self.parse_detail,
                                 dont_filter=self.full_scan)

        # ------------------------------------------------------------------
        # API pagination – deeper history (offsets 10..190, step 10)
        # ------------------------------------------------------------------
        for offset in range(10, 200, 10):
            api_url = (
                'https://www.bloomberg.com/lineup-next/api/paginate'
                f'?id=story-list-1&page=jp-economics&offset={offset}'
                '&variation=archive&type=lineup_content&locale=ja'
            )
            yield scrapy.Request(api_url, callback=self.parse_api_json,
                                 dont_filter=True)

    # ------------------------------------------------------------------
    # API pagination handler
    # ------------------------------------------------------------------
    def parse_api_json(self, response):
        try:
            data = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse Bloomberg API JSON: {e}")
            return

        # Locate the items list inside the paginated payload
        items = []
        if 'story-list-1' in data:
            items = data['story-list-1'].get('items', [])
        else:
            items = self._deep_find_items(data) or []

        has_valid_item_in_window = False
        for item in items:
            raw_url = item.get('url')
            if not raw_url:
                continue
            url = response.urljoin(raw_url)
            if not self.should_process(url):
                continue
            has_valid_item_in_window = True
            yield scrapy.Request(url, callback=self.parse_detail,
                                 dont_filter=self.full_scan)

        if not has_valid_item_in_window:
            self.logger.info(
                f"API offset exhausted – no new URLs on {response.url}"
            )

    # ------------------------------------------------------------------
    # Detail page
    # ------------------------------------------------------------------
    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )

        # Re-check with the publish_time that auto_parse_item extracted from the page
        if not self.should_process(response.url, item.get('publish_time')):
            return

        item['author'] = 'Bloomberg'
        item['section'] = 'Economics'

        yield item

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _collect_urls(obj, base_url, found_urls):
        """Recursively walk a deserialised JSON tree and collect /news/articles/ URLs."""
        if isinstance(obj, dict):
            candidate = obj.get('url')
            if isinstance(candidate, str) and '/news/articles/' in candidate:
                found_urls.add(urljoin(base_url, candidate))
            for v in obj.values():
                BloombergSpider._collect_urls(v, base_url, found_urls)
        elif isinstance(obj, list):
            for item in obj:
                BloombergSpider._collect_urls(item, base_url, found_urls)

    @staticmethod
    def _deep_find_items(obj):
        """Fallback: recursively find the first 'items' list in a nested dict."""
        if isinstance(obj, dict):
            if 'items' in obj and isinstance(obj['items'], list):
                return obj['items']
            for v in obj.values():
                res = BloombergSpider._deep_find_items(v)
                if res:
                    return res
        return None
