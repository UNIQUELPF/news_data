import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider
from scrapy_playwright.page import PageMethod


class PlParkietSpider(SmartSpider):
    name = "pl_parkiet"
    country_code = 'POL'
    country = '波兰'
    language = 'pl'
    source_timezone = 'Europe/Warsaw'
    start_date = '2024-01-01'
    allowed_domains = ["www.parkiet.com"]
    start_urls = ["https://www.parkiet.com/wiadomosci"]
    fallback_content_selector = '.articleBody.body'

    use_curl_cffi = True
    strict_date_required = False

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True}
    }

    def start_requests(self):
        yield scrapy.Request(
            self.start_urls[0],
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "a.contentLink"),
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
        page = response.meta.get("playwright_page")

        links = response.css('a.contentLink::attr(href)').getall()
        unique_links = list(set(links))

        for link in unique_links:
            if not link.startswith('http'):
                link = "https://www.parkiet.com" + link

            if self.should_process(link):
                yield scrapy.Request(
                    link,
                    callback=self.parse_article,
                    meta={"playwright": True}
                )

        if page:
            await page.close()

    def parse_article(self, response):
        # Custom date extraction (DD.MM.YYYY HH:MM)
        date_str = response.css('span#livePublishedAtContainer::text').get()
        pub_date = None
        if date_str:
            try:
                pub_date = datetime.strptime(date_str.strip(), "%d.%m.%Y %H:%M")
                pub_date = self.parse_to_utc(pub_date)
            except Exception as e:
                self.logger.warning(f"Could not parse Polish date '{date_str}': {e}")

        item = self.auto_parse_item(response)
        item['publish_time'] = pub_date or item.get('publish_time')
        item['author'] = (response.css('.author .name a::text').get() or "Parkiet.com").strip()
        item['section'] = 'Markets'

        if not self.should_process(response.url, item.get('publish_time')):
            return

        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
