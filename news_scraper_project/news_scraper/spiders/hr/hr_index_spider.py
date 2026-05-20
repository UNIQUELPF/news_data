import scrapy
import re
import dateparser
from news_scraper.spiders.smart_spider import SmartSpider
from scrapy_playwright.page import PageMethod


class HrIndexSpider(SmartSpider):
    name = "hr_index"
    source_timezone = 'Europe/Zagreb'

    country_code = 'HRV'
    country = '克罗地亚'
    language = 'hr'
    dateparser_settings = {"DATE_ORDER": "DMY"}

    allowed_domains = ["www.index.hr"]
    start_urls = ["https://www.index.hr/vijesti/rubrika/hrvatska/22.aspx"]

    # Croatian months mapping (genitive case)
    MONTHS_HR = {
        "siječnja": 1,
        "veljače": 2,
        "ožujka": 3,
        "travnja": 4,
        "svibnja": 5,
        "lipnja": 6,
        "srpnja": 7,
        "kolovoza": 8,
        "rujna": 9,
        "listopada": 10,
        "studenoga": 11,
        "prosinca": 12
    }

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True}
    }

    use_curl_cffi = True
    strict_date_required = False  # Listing cards lack structured date elements

    fallback_content_selector = '.text'

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "a.vijesti-text-hover", timeout=15000),
                    ]
                },
                dont_filter=True,
            )

    def parse(self, response):
        """
        Parse listing page with 'Load More' pagination.
        SmartSpider V2: extracts dates, uses should_process() with circuit breaker.
        """
        anchors = response.css('a.vijesti-text-hover')
        has_valid_item_in_window = False

        for a in anchors:
            link = a.css('::attr(href)').get()
            if not link or '/clanak/' not in link:
                continue

            if not link.startswith('http'):
                link = "https://www.index.hr" + link

            # Extract date from listing card (look in ancestor container)
            publish_time = self._extract_listing_date(a)

            if not self.should_process(link, publish_time):
                continue

            has_valid_item_in_window = True

            # Capture the listing title as a hint for the detail page
            title_hint = a.css('::text').get() or a.css('::attr(title)').get() or a.css('::attr(aria-label)').get()

            yield scrapy.Request(
                link,
                callback=self.parse_article,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "h1", timeout=10000),
                    ],
                    "title_hint": title_hint.strip() if title_hint else None,
                    "publish_time_hint": publish_time,
                },
                dont_filter=self.full_scan,
            )

        # 'Load More' Pagination -- only continue if we found articles in window
        if has_valid_item_in_window:
            yield scrapy.Request(
                response.url,
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("click", ".btn-read-more"),
                        PageMethod("wait_for_timeout", 3000),
                        PageMethod("wait_for_selector", "a.vijesti-text-hover", timeout=5000),
                    ]
                },
                dont_filter=True,
            )

    def _extract_listing_date(self, anchor_sel):
        """
        Extract publish date from the listing card containing the anchor element.
        Index.hr cards use a <time> element or .publish-date div/span inside the anchor.
        Returns a naive UTC datetime or None.
        """
        # Strategy 1: <time> element with datetime attribute
        time_el = anchor_sel.css('time')
        if time_el:
            dt_attr = time_el.xpath('@datetime').get()
            if dt_attr:
                parsed = self.parse_date(dt_attr)
                if parsed:
                    return parsed
            time_text = time_el.xpath('text()').get()
            if time_text:
                parsed = self.parse_date(time_text.strip())
                if parsed:
                    return parsed

        # Strategy 2: .publish-date text
        date_text = anchor_sel.css('.publish-date::text').get()
        if date_text:
            return self.parse_date(date_text.strip())

        return None

    def _parse_croatian_date(self, text):
        """
        Parse a Croatian datetime string like '17:45, 06. travnja 2026.'.
        Uses the MONTHS_HR mapping (genitive case).
        """
        match = re.search(r'(\d{2}:\d{2}),\s*(\d{2})\.\s*(\w+)\s*(\d{4})\.', text)
        if not match:
            return None

        try:
            time_part = match.group(1)
            day_part = int(match.group(2))
            month_name = match.group(3).lower()
            year_part = int(match.group(4))

            month_part = self.MONTHS_HR.get(month_name)
            if not month_part:
                return None

            from datetime import datetime
            h, m = int(time_part.split(':')[0]), int(time_part.split(':')[1])
            dt_obj = datetime(year_part, month_part, day_part, h, m)
            return self.parse_to_utc(dt_obj)
        except Exception:
            self.logger.warning(f"Date parse failed for listing text: {text}")
            return None

    def parse_date(self, date_str: str):
        if not date_str:
            return None
        # Try custom Croatian parser first
        parsed = self._parse_croatian_date(date_str.strip())
        if parsed:
            return parsed
        # Fall back to base class parse_date
        return super().parse_date(date_str)

    def parse_article(self, response):
        """
        Parse article detail page using SmartSpider V2 auto_parse_item.
        """
        # Try JSON-LD first for robust date and title extraction
        pub_time = None
        for ld in response.css('script[type="application/ld+json"]::text').getall():
            try:
                import json
                data = json.loads(ld)
                if isinstance(data, list):
                    data = data[0]
                ds = data.get('datePublished') or data.get('dateCreated')
                if ds:
                    pub_time = self.parse_date(ds)
                    if pub_time:
                        break
            except Exception:
                continue

        item = self.auto_parse_item(
            response,
            title_xpath="//meta[@property='og:title']/@content",
        )

        if pub_time:
            item['publish_time'] = pub_time

        # Override specific fields
        item['author'] = "Index.hr"
        item['section'] = "News"

        yield item
