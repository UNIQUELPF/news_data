# 哈萨克斯坦lsm spider爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from scrapy_playwright.page import PageMethod


class LSMSpider(SmartSpider):
    name = 'lsm'

    country_code = 'KAZ'
    country = '哈萨克斯坦'
    language = 'ru'
    source_timezone = 'Asia/Almaty'

    allowed_domains = ['lsm.kz']

    fallback_content_selector = '#mainArticleLeftTextFulltext'

    # Sections to scrape
    SECTIONS = {
        'Analytics': 'https://lsm.kz/analytics',
        'Banks': 'https://lsm.kz/banks',
        'Exchange': 'https://lsm.kz/exchange',
        'Property': 'https://lsm.kz/property',
        'Appointments': 'https://lsm.kz/appointments',
        'Taxes': 'https://lsm.kz/taxes',
        'Projects': 'https://lsm.kz/projects',
        'Freedom': 'https://lsm.kz/freedom',
        'Markets': 'https://lsm.kz/markets',
        'Company': 'https://lsm.kz/company',
        'Auto': 'https://lsm.kz/auto',
        'Infographics': 'https://lsm.kz/infographics',
        'Archive': 'https://lsm.kz/archive'
    }

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,  # Serial: one-by-one detail check
        'DOWNLOAD_DELAY': 1.5,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'PLAYWRIGHT_MAX_CONTEXTS': 2,
        'PLAYWRIGHT_MAX_PAGES_PER_CONTEXT': 2,
    }

    async def start(self):
        for category, url in self.SECTIONS.items():
            yield scrapy.Request(
                url,
                callback=self.parse_list,
                meta={
                    'category': category,
                    'page': 1,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_timeout', 2000),
                        PageMethod('wait_for_selector', '#mainInnerRightGrid', timeout=20000)
                    ]
                },
                dont_filter=True,
            )

    def parse_list(self, response):
        if self._stop_pagination:
            return
        category = response.meta['category']
        current_page = response.meta['page']

        # Scrape articles on current page
        articles = response.css('#mainInnerRightGrid a[href^="/"]')
        self.logger.info(f"[{category}] Found {len(articles)} articles on page {current_page}")

        has_valid_item_in_window = False

        for art in articles:
            # Extract basic info from list
            link = art.css('::attr(href)').get()
            title = art.css('.innerGridElemTxt::text').get()
            date_str = art.css('.innerGridElemDate::text').get()

            if not link:
                continue

            url = response.urljoin(link)
            publish_time = self.parse_date(date_str) if date_str else None

            if not self.should_process(url, publish_time):
                continue

            has_valid_item_in_window = True

            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    'category': category,
                    'title_hint': title.strip() if title else None,
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

        # Pagination: only continue if we found articles in the window
        if has_valid_item_in_window:
            next_page = current_page + 1
            section_url = self.SECTIONS[category]
            next_url = f"{section_url}/!{next_page}"

            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={
                    'category': category,
                    'page': next_page,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_timeout', 2000),
                        PageMethod('wait_for_selector', '#mainInnerRightGrid', timeout=20000)
                    ]
                },
                dont_filter=True,
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[@id='mainArticleLeftTextTopRightHead']/text()",
            publish_time_xpath="//div[@id='mainArticleLeftTextTopRightStatDate']/text()",
        )

        # Final safety check on publish_time (V2 requirement)
        if item.get('publish_time') and not self.should_process(response.url, item['publish_time']):
            self._stop_pagination = True
            return

        # Reject articles with excessively short content
        content_plain = item.get('content_plain') or ''
        if len(content_plain) < 100:
            self.logger.warning(f"Rejected {response.url}: content too short ({len(content_plain)} chars)")
            return

        item['section'] = response.meta.get('section_hint', 'news')
        item['author'] = 'lsm.kz'

        yield item
