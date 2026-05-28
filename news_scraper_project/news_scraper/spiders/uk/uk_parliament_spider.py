import scrapy
import re
from urllib.parse import urljoin
from news_scraper.spiders.smart_spider import SmartSpider


async def init_page(page, request):
    from playwright_stealth import stealth_async
    await stealth_async(page)
    # Block fonts, images, stylesheets, and media to save bandwidth and speed up loading
    await page.route(
        "**/*",
        lambda route: route.abort()
        if route.request.resource_type in ["image", "media", "font", "stylesheet"]
        else route.continue_()
    )


class UkParliamentSpider(SmartSpider):
    name = "uk_parliament"
    source_timezone = 'Europe/London'

    country_code = 'GBR'
    country = '英国'
    language = 'en'
    allowed_domains = ["parliament.uk"]

    fallback_content_selector = "article, [role='main'], main, .content, #content"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
    }

    use_curl_cffi = True

    @property
    def playwright_meta(self):
        return {
            "playwright": True,
            "playwright_context": "uk_parliament",
            "playwright_context_kwargs": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            },
            "playwright_page_goto_kwargs": {
                "wait_until": "domcontentloaded",
                "timeout": 60000,
            },
            "playwright_page_init_callback": "news_scraper.spiders.uk.uk_parliament_spider.init_page",
        }

    async def start(self):
        yield scrapy.Request(
            "https://www.parliament.uk/business/news/parliament-government-and-politics/parliament/commons-news/?page=1",
            callback=self.parse_listing,
            meta=self.playwright_meta,
            dont_filter=True
        )
        yield scrapy.Request(
            "https://www.parliament.uk/business/news/parliament-government-and-politics/parliament/lords-news/?page=1",
            callback=self.parse_listing,
            meta=self.playwright_meta,
            dont_filter=True
        )

    def parse_listing(self, response):
        """Parse listing page with cards and pagination circuit breaker."""
        cards = response.css('a.card.card-content')
        if not cards:
            self.logger.info(f"No cards found on {response.url}")
            return

        has_valid_item_in_window = False
        for card in cards:
            link = card.attrib.get('href')
            if not link:
                continue
            full_url = urljoin(response.url, link)

            # Extract date from card info
            date_str = card.css('.indicator::text').get()
            if not date_str:
                date_str = card.css('.indicator-label::text').get()
            
            publish_time = self.parse_date(date_str.strip()) if date_str else None

            if not self.should_process(full_url, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
                meta={
                    "original_url": full_url,
                    "publish_time_hint": publish_time,
                    **self.playwright_meta
                }
            )

        # Pagination with circuit breaker
        if has_valid_item_in_window:
            current_page = 1
            match = re.search(r'page=(\d+)', response.url)
            if match:
                current_page = int(match.group(1))

            next_page = current_page + 1
            next_url = re.sub(
                r'page=\d+', f'page={next_page}', response.url
            )
            yield scrapy.Request(
                next_url,
                callback=self.parse_listing,
                meta=self.playwright_meta
            )

    def parse_article(self, response):
        """Parse direct Playwright response for article content."""
        url = response.meta["original_url"]
        section = self._get_section(url)

        item = self.auto_parse_item(
            response,
            title_xpath="//meta[@property='og:title']/@content | //h1/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content | //meta[@name='dcterms.created']/@content | //meta[@name='dc.date']/@content | //meta[@name='publishdate']/@content | //p[contains(@class, 'sub-heading')]/text()",
        )
        
        title = item.get("title") or ""
        if "just a moment" in title.lower():
            self.logger.warning(f"Cloudflare block page detected on {url}. Discarding.")
            return

        if item.get('content_plain') and len(item['content_plain']) > 50:
            item["url"] = url
            item["section"] = section
            item["author"] = "UK Parliament"
            yield item
        else:
            self.logger.warning(f"Direct extraction failed or too short for {url}")

    def _get_section(self, url):
        """Determine article section from URL."""
        if "committee" in url:
            return "Committees"
        return "Commons" if "commons-news" in url else "Lords"
