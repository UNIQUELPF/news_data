# 哈萨克斯坦digitalbusiness spider爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from scrapy_playwright.page import PageMethod
from news_scraper.spiders.smart_spider import SmartSpider


class DigitalBusinessSpider(SmartSpider):
    name = 'digitalbusiness'

    country_code = 'KAZ'
    country = '哈萨克斯坦'
    language = 'ru'
    source_timezone = 'Asia/Almaty'

    allowed_domains = ['digitalbusiness.kz']

    start_date = '2025-01-01'
    fallback_content_selector = '.content_col'

    # Base URL
    BASE_URL = 'https://digitalbusiness.kz'

    # Sections to scrape
    SECTIONS = {
        'IT-Startups': '/it-i-startapy/',
        'Finance': '/finance/',
        'Latest': '/last/'
    }

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,  # Serial: listing-no-date, detail check one-by-one
        'DOWNLOAD_DELAY': 1.0,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'PLAYWRIGHT_MAX_CONTEXTS': 4,
        'PLAYWRIGHT_MAX_PAGES_PER_CONTEXT': 2,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    async def start(self):
        for category, path in self.SECTIONS.items():
            url = self.BASE_URL + path
            yield scrapy.Request(
                url,
                callback=self.parse_list,
                meta={
                    'category': category,
                    'page': 1,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_selector', 'a.pcb_wrap', timeout=30000)
                    ]
                },
                dont_filter=True,
            )

    def parse_date(self, date_str):
        """Pre-clean Russian date prefixes and parse with Russian locale."""
        if date_str:
            date_str = date_str.lower().strip()
            if 'дата публикации:' in date_str:
                date_str = date_str.replace('дата публикации:', '').strip()
        if not date_str:
            return None
        import dateparser
        parsed = dateparser.parse(date_str, languages=['ru'])
        if parsed:
            return self.parse_to_utc(parsed)
        return None

    def parse_list(self, response):
        if self._stop_pagination:
            return
        category = response.meta['category']
        current_page = response.meta['page']

        self.logger.info(f"[{category}] Page {current_page} response length: {len(response.body)}")

        articles = response.css('a.pcb_wrap')
        if not articles:
            articles = response.xpath('//a[contains(@class, "pcb_wrap")]')

        self.logger.info(f"[{category}] Found {len(articles)} article links on page {current_page}")

        has_valid_item_in_window = False

        for art in articles:
            link = art.css('::attr(href)').get()
            title = art.css('.pcb_title::text').get()
            date_str = art.css('.pcb_date::text').get()

            if not link:
                continue

            url = response.urljoin(link)
            publish_time = self.parse_date(date_str)

            if not self.should_process(url, publish_time):
                continue

            has_valid_item_in_window = True

            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    'category': category,
                    'title_hint': title,
                    'publish_time_hint': publish_time,
                    'section_hint': category,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_timeout', 1500),
                        PageMethod('wait_for_selector', 'h1', timeout=15000)
                    ]
                },
                dont_filter=self.full_scan,
            )

        # Pagination: only continue when we found items within the window
        if has_valid_item_in_window:
            next_page = current_page + 1
            section_path = self.SECTIONS[category]
            next_url = f"{self.BASE_URL}{section_path}/page/{next_page}/"

            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={
                    'category': category,
                    'page': next_page,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_timeout', 2000),
                        PageMethod('wait_for_selector', 'a.pcb_wrap', timeout=20000)
                    ]
                },
                dont_filter=True,
            )

    def parse_detail(self, response):
        # Try detail page date (may include time, more precise than list-page date)
        date_text = response.xpath('//p[contains(text(), "Дата публикации")]/text()').get()
        if not date_text:
            date_text = response.css('time::text').get()
        detail_publish_time = self.parse_date(date_text)

        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
        )

        # Prefer detail page date over list page hint when available
        if detail_publish_time:
            item['publish_time'] = detail_publish_time

        if not self.should_process(response.url, item.get('publish_time')):
            self._stop_pagination = True
            return

        # Skip items with insufficient content
        content_text = item.get('content_plain') or item.get('content') or ''
        if not item.get('title') or len(content_text) < 100:
            return

        yield item
