import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider
from scrapy_playwright.page import PageMethod

class PlParkietSpider(BaseNewsSpider):
    name = "pl_parkiet"
    allowed_domains = ["www.parkiet.com"]
    start_urls = ["https://www.parkiet.com/wiadomosci"]
    target_table = "pl_parkiet_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2, # Low for Playwright listing page stability
        "DOWNLOAD_DELAY": 1.5,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True}
    }

    use_curl_cffi = True

    def start_requests(self):
        # We use Playwright on the listing page to handle infinite scroll
        # We'll scroll down a few times to get enough articles for the test/start
        yield scrapy.Request(
            self.start_urls[0],
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "a.contentLink"),
                    # Scroll down 5 times to load more content
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                    PageMethod("wait_for_timeout", 2000),
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                    PageMethod("wait_for_timeout", 2000),
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                    PageMethod("wait_for_timeout", 2000),
                ]
            }
        )

    async def parse(self, response):
        """
        Parse listing page with loaded content.
        """
        page = response.meta.get("playwright_page")
        if page:
             # Just to be safe, we close the page if we don't need it further
             # But here we extract first.
             pass

        links = response.css('a.contentLink::attr(href)').getall()
        # Deduplicate
        unique_links = list(set(links))
        
        for link in unique_links:
            if not link.startswith('http'):
                link = "https://www.parkiet.com" + link

            # Persistent memory fingerprint check
            if link in self.scraped_urls:
                continue
            
            yield scrapy.Request(
                link, 
                callback=self.parse_article,
                # Detail pages also have dates rendered via JS potentially
                meta={"playwright": True}
            )
        
        if page:
            await page.close()

    def parse_article(self, response):
        # Title extraction
        title = response.css('h1.article--title::text').get()
        if not title:
            title = response.css('title::text').get()
        
        # Publication Date (Format: 03.04.2026 06:00)
        date_str = response.css('span#livePublishedAtContainer::text').get()
        pub_date = None
        if date_str:
            try:
                # DD.MM.YYYY HH:MM
                pub_date = datetime.strptime(date_str.strip(), "%d.%m.%Y %H:%M")
            except Exception as e:
                self.logger.warning(f"Could not parse Polish date '{date_str}': {e}")

        # Date filtering (default 2026-01-01)
        if pub_date and not self.filter_date(pub_date):
            return

        # Content extraction from .articleBody
        content_nodes = response.css('.articleBody.body p::text, .articleBody.body li::text').getall()
        content = "\n".join([c.strip() for c in content_nodes if c.strip()])

        if not content:
             content_nodes = response.css('.article--content p::text').getall()
             content = "\n".join([c.strip() for c in content_nodes if c.strip()])

        author = response.css('.author .name a::text').get() or "Parkiet.com"

        if title and content:
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": pub_date,
                "author": author.strip(),
                "language": "pl",
                "section": "Markets"
            }
