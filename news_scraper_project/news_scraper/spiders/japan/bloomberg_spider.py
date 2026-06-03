import scrapy
import json
import re
from urllib.parse import urljoin
from scrapy_playwright.page import PageMethod

from news_scraper.spiders.smart_spider import SmartSpider


class BloombergSpider(SmartSpider):
    name = 'jp_bloomberg'

    country_code = 'JPN'
    country = '日本'
    language = 'en'
    source_timezone = 'Asia/Tokyo'

    allowed_domains = ['bloomberg.com']
    start_urls = ['https://www.bloomberg.com/jp/economics']

    fallback_content_selector = '.body-copy, article'

    # Bloomberg API list endpoints don't expose publish dates on item cards,
    # so we defer date-dependent filtering to the detail page.
    strict_date_required = False

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
            'timeout': 60000,
        },
    }

    async def start(self):
        js_scroll = """
        async () => {
            for (let i = 0; i < 5; i++) {
                window.scrollBy(0, window.innerHeight * 2);
                await new Promise(r => setTimeout(r, 1500));
            }
        }
        """
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_list,
                dont_filter=True,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "domcontentloaded"),
                        PageMethod("evaluate", js_scroll),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                }
            )

    # ------------------------------------------------------------------
    # Listing page – embedded JSON
    # ------------------------------------------------------------------
    async def parse_list(self, response):
        """Extract article links from DOM after scroll and scrape sequentially using the same page context."""
        page = response.meta.get("playwright_page")
        if not page:
            self.logger.error("No playwright page found in meta!")
            return

        found_urls = set()
        
        # 1. Extract from standard a href links in the DOM
        links = response.xpath("//a[contains(@href, '/news/articles/')]/@href").getall()
        for link in links:
            found_urls.add(response.urljoin(link))
            
        # 2. Extract from embedded initialState JSON blob as fallback
        scripts = response.xpath('//script[contains(text(), "initialState")]/text()').getall()
        for script_text in scripts:
            try:
                data = json.loads(script_text)
                self._collect_urls(data, response.url, found_urls)
            except Exception:
                pass

        self.logger.info(
            f"Bloomberg List: Found {len(found_urls)} initial article links after scroll & JSON."
        )

        try:
            for url in found_urls:
                if not self.should_process(url):          # dedup-only (strict_date_required=False)
                    continue
                
                self.logger.info(f"Sequentially scraping detail via single page context: {url}")
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    await page.wait_for_timeout(2000)
                    
                    html_content = await page.content()
                    fake_response = scrapy.http.HtmlResponse(
                        url=url,
                        body=html_content,
                        encoding='utf-8'
                    )
                    
                    # Manual extraction using parse_detail selector
                    for item in self.parse_detail(fake_response):
                        yield item
                except Exception as ex:
                    self.logger.error(f"Sequential scrape error on {url}: {ex}")
        finally:
            await page.close()

    # ------------------------------------------------------------------
    # Detail page
    # ------------------------------------------------------------------
    def parse_date(self, date_str: str):
        if not date_str:
            return None
        date_str = date_str.strip()
        
        import re
        from datetime import datetime, timedelta
        
        # 1. Handle relative Japanese hours "X 時間前"
        match_hour = re.search(r'(\d+)\s*時間前', date_str)
        if match_hour:
            hours = int(match_hour.group(1))
            dt = datetime.now() - timedelta(hours=hours)
            return self.parse_to_utc(dt)
            
        # 2. Handle relative Japanese minutes "X 分前"
        match_min = re.search(r'(\d+)\s*分前', date_str)
        if match_min:
            mins = int(match_min.group(1))
            dt = datetime.now() - timedelta(minutes=mins)
            return self.parse_to_utc(dt)
            
        # 3. Handle relative Japanese days "X 日前"
        match_day = re.search(r'(\d+)\s*日前', date_str)
        if match_day:
            days = int(match_day.group(1))
            dt = datetime.now() - timedelta(days=days)
            return self.parse_to_utc(dt)

        return super().parse_date(date_str)

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )

        if not item.get('publish_time'):
            url_date_match = re.search(r'/articles/(\d{4}-\d{2}-\d{2})/', response.url)
            if url_date_match:
                item['publish_time'] = self.parse_date(url_date_match.group(1))

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
