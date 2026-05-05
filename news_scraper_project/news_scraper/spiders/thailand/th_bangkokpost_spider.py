import scrapy
import re
import json
from datetime import datetime
from scrapy.selector import Selector
from news_scraper.spiders.smart_spider import SmartSpider


class ThBangkokpostSpider(SmartSpider):
    name = "th_bangkokpost"
    source_timezone = 'Asia/Bangkok'
    country_code = 'THA'
    country = '泰国'
    language = 'en'

    allowed_domains = ['bangkokpost.com']
    start_url = 'https://www.bangkokpost.com/business/general'

    use_curl_cffi = True
    fallback_content_selector = "article"
    strict_date_required = True

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'PLAYWRIGHT_LAUNCH_OPTIONS': {'headless': True},
    }

    async def start(self):
        yield scrapy.Request(
            self.start_url,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_init_callback": self.block_resources,
            },
            callback=self.parse
        )

    async def block_resources(self, page, request):
        """Block unnecessary resources to speed up Playwright rendering."""
        if request.resource_type in ["image", "media", "font", "stylesheet"]:
            await request.abort()
            return
        if "googletagservices" in request.url or "google-analytics" in request.url:
            await request.abort()
            return

    async def parse(self, response):
        page = response.meta["playwright_page"]

        has_valid_item_in_window = False

        # Initial batch of articles
        links = response.css('h3 a::attr(href)').getall()
        for link in links:
            if '/business/general/' in link:
                yield response.follow(link, self.parse_article)
                has_valid_item_in_window = True

        # Click MORE while we still found articles in the previous batch
        for _ in range(30):
            if not has_valid_item_in_window:
                break
            try:
                more_button = await page.wait_for_selector('#page--link a', timeout=5000)
                if not more_button:
                    break

                await more_button.click()
                await page.wait_for_timeout(2000)

                content = await page.content()
                new_selector = Selector(text=content)
                new_links = new_selector.css('h3 a::attr(href)').getall()

                batch_has_items = False
                for link in new_links:
                    if '/business/general/' in link:
                        yield response.follow(link, self.parse_article)
                        batch_has_items = True

                has_valid_item_in_window = batch_has_items
            except Exception as e:
                self.logger.info(f"Stop clicking MORE: {e}")
                break

        await page.close()

    def parse_article(self, response):
        # ---- Date extraction with extensive fallbacks ----
        pub_time = None

        # 1. meta[name="lead:published_at"] (most accurate)
        date_str = response.css('meta[name="lead:published_at"]::attr(content)').get()
        if date_str:
            try:
                pub_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except Exception:
                pass

        # 2. meta[property="article:published_time"]
        if not pub_time:
            date_str = response.css('meta[property="article:published_time"]::attr(content)').get()
            if date_str:
                try:
                    pub_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except Exception:
                    pass

        # 3. Visible text: "PUBLISHED : 31 Mar 2026 at 01:01"
        if not pub_time:
            text_date = response.css('.article-info--col > p::text').get('')
            match = re.search(r'(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})', text_date)
            if match:
                d, m_str, y = match.groups()
                months = {
                    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                }
                m = months.get(m_str)
                if m:
                    try:
                        pub_time = datetime(int(y), m, int(d))
                    except Exception:
                        pass

        # 4. LD+JSON
        if not pub_time:
            ld_jsons = response.css('script[type="application/ld+json"]::text').getall()
            for ld in ld_jsons:
                try:
                    data = json.loads(ld)
                    if isinstance(data, list):
                        data = data[0]
                    ds = data.get('datePublished')
                    if ds:
                        pub_time = datetime.fromisoformat(ds.replace('Z', '+00:00'))
                        break
                except Exception:
                    continue

        # Convert to UTC
        if pub_time:
            pub_time = self.parse_to_utc(pub_time)

        # Date filtering via should_process
        if not self.should_process(response.url, pub_time):
            return

        # ---- Standard extraction via auto_parse_item ----
        item = self.auto_parse_item(response)

        # ---- Override with precise custom extraction ----
        item['publish_time'] = pub_time

        title = response.css('h1::text').get('').strip()
        if not title:
            title = response.css('title::text').get('').replace(' - Bangkok Post', '').strip()
        if title:
            item['title'] = title

        paragraphs = response.css('.article-content p::text').getall()
        if paragraphs:
            content = "\n\n".join([p.strip() for p in paragraphs if p.strip()])
            item['content_plain'] = content

        item['author'] = response.css('meta[name="author"]::attr(content)').get() or 'Bangkok Post'
        item['section'] = 'Business/General'

        yield item
