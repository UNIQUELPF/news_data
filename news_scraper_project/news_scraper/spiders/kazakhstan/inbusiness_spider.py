# 哈萨克斯坦inbusiness spider爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
import re
from datetime import datetime, timedelta
from scrapy_playwright.page import PageMethod
from news_scraper.spiders.smart_spider import SmartSpider


class InBusinessSpider(SmartSpider):
    name = 'inbusiness'

    country_code = 'KAZ'
    country = '哈萨克斯坦'
    language = 'ru'
    source_timezone = 'Asia/Almaty'

    allowed_domains = ['inbusiness.kz']

    # Russian date format (DD.MM.YY) used in listing
    dateparser_settings = {'DATE_ORDER': 'DMY', 'PREFER_DATES_FROM': 'current_period'}

    fallback_content_selector = '.text'

    # Base URL for categories
    BASE_URL = 'https://inbusiness.kz'

    # Sections to scrape from the menu
    SECTIONS = {
        'Business': '/ru/cat/biznes',
        'Finance': '/ru/cat/finansy',
        'Economy': '/ru/cat/ekonomika',
        'Country': '/ru/cat/strana',
        'Property': '/ru/cat/nedvizhimost',
        'World': '/ru/cat/mir',
        'Tech': '/ru/cat/tehnologii',
        'Auto': '/ru/cat/avto',
        'Sport': '/ru/cat/sport',
        'Lifestyle': '/ru/cat/stil-zhizni',
        'Experts': '/ru/authors',
        'Appointments': '/ru/appointments'
    }

    custom_settings = {
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1.0,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'PLAYWRIGHT_MAX_CONTEXTS': 4,
        'PLAYWRIGHT_MAX_PAGES_PER_CONTEXT': 2,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    def start_requests(self):
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
                        PageMethod('wait_for_timeout', 2000),
                        PageMethod('wait_for_selector', 'a[href^="/ru/news/"]', timeout=20000)
                    ]
                }
            )

    def parse_list(self, response):
        category = response.meta['category']
        current_page = response.meta['page']

        articles = response.css('a[href^="/ru/news/"]')
        self.logger.info(f"[{category}] Found {len(articles)} article links on page {current_page}")

        has_valid_item_in_window = False

        for art in articles:
            link = art.css('::attr(href)').get()
            title = art.css('span::text').get()
            date_str = art.css('time::text').get()

            if not link:
                continue

            url = response.urljoin(link)
            publish_time = self._parse_listing_date(date_str)

            if not self.should_process(url, publish_time):
                continue

            has_valid_item_in_window = True

            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    'category': category,
                    'section_hint': category,
                    'title_hint': title,
                    'publish_time_hint': publish_time,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_timeout', 1500),
                        PageMethod('wait_for_selector', 'h1', timeout=15000)
                    ]
                },
                dont_filter=self.full_scan,
            )

        # Pagination: ?page=N
        if has_valid_item_in_window:
            next_page = current_page + 1
            section_path = self.SECTIONS[category]
            next_url = f"{self.BASE_URL}{section_path}?page={next_page}"

            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={
                    'category': category,
                    'page': next_page,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_timeout', 2000),
                        PageMethod('wait_for_selector', 'a[href^="/ru/news/"]', timeout=20000)
                    ]
                }
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//time/@datetime",
        )

        if not self.should_process(response.url, item.get('publish_time')):
            return

        # Basic validation: require title and >= 100 chars of content
        title = item.get('title')
        content = item.get('content_plain') or item.get('content', '')
        if not title or len(content) < 100:
            return

        yield item

    def _parse_listing_date(self, date_str):
        """Parse date from listing page.

        Handles Russian date formats:
        - '02.03.26, 09:00' (DD.MM.YY, HH:MM)
        - 'Вчера, 18:30' (Yesterday)
        - 'Сегодня, 10:00' (Today)
        - '20.02.26' (DD.MM.YY without time)
        """
        if not date_str:
            return None

        date_str = date_str.strip()

        # Try dateparser first (handles Russian 'Вчера', 'Сегодня' and standard formats)
        parsed = self.parse_date(date_str)
        if parsed:
            return parsed

        # Fallback for edge cases
        return self._parse_russian_date_fallback(date_str)

    def _parse_russian_date_fallback(self, date_str):
        """Fallback date parser for edge cases that dateparser might miss."""
        now = datetime.now()

        try:
            if 'Сегодня' in date_str:
                time_part = re.search(r'(\d{2}:\d{2})', date_str)
                if time_part:
                    h, m = map(int, time_part.group(1).split(':'))
                    return self.parse_to_utc(now.replace(hour=h, minute=m, second=0, microsecond=0))
                return self.parse_to_utc(now)

            if 'Вчера' in date_str:
                yesterday = now - timedelta(days=1)
                time_part = re.search(r'(\d{2}:\d{2})', date_str)
                if time_part:
                    h, m = map(int, time_part.group(1).split(':'))
                    return self.parse_to_utc(yesterday.replace(hour=h, minute=m, second=0, microsecond=0))
                return self.parse_to_utc(yesterday)

            # Format: DD.MM.YY, HH:MM or DD.MM.YY
            match = re.search(r'(\d{2})\.(\d{2})\.(\d{2})(?:,\s*(\d{1,2}):(\d{2}))?', date_str)
            if match:
                day, month, year, hour, minute = match.groups()
                full_year = 2000 + int(year)
                h = int(hour) if hour else 0
                m = int(minute) if minute else 0
                dt = datetime(full_year, int(month), int(day), h, m)
                return self.parse_to_utc(dt)
        except Exception:
            pass

        return None
