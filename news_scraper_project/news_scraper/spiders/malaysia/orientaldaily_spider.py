# 马来西亚东方日报爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class OrientalDailySpider(SmartSpider):
    name = "malaysia_orientaldaily"

    country_code = "MYS"
    country = "马来西亚"
    language = "zh"
    source_timezone = "Asia/Kuala_Lumpur"
    use_curl_cffi = True
    dateparser_settings = {"DATE_ORDER": "DMY"}

    fallback_content_selector = '[itemprop="articleBody"]'

    allowed_domains = ["orientaldaily.com.my"]

    MAX_PAGES = 50

    # Business section
    BASE_URL = "https://www.orientaldaily.com.my/news/business?page={page}"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS': 1,  # Serial: one-by-one detail check
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 543,
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        },
        'CURLL_CFFI_IMPERSONATE': 'chrome120',
    }

    async def start(self):
        yield scrapy.Request(
            self.BASE_URL.format(page=1),
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True,
        )

    def parse_list(self, response):
        page = response.meta.get('page', 1)
        items = response.css('div.news-item')
        if not items:
            self.logger.info(f"No more items on page {page}")
            return

        self.logger.info(f"Page {page}: found {len(items)} items")
        valid_links = []
        meta_hints = {}

        for item in items:
            url = item.css('a.link ::attr(href)').get()
            title = item.css('h3 ::text').get()
            time_str = item.css('time ::attr(datetime)').get()

            if not url or not time_str:
                continue

            # Standard format: 2026-03-25 14:39:00
            try:
                dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            except Exception as e:
                self.logger.error(f"Failed to parse time {time_str}: {e}")
                continue

            publish_time = self.parse_to_utc(dt)

            if not self.should_process(url, publish_time):
                continue

            valid_links.append(url)
            meta_hints[url] = (title.strip() if title else None, publish_time)

        if not valid_links:
            self.logger.info(f"[{self.name}] No valid links in window on page {page}. Stopping.")
            return

        state = {
            'pending_count': len(valid_links),
            'dates': [],
            'page': page,
            'response_url': response.url
        }

        for url in valid_links:
            title_hint, publish_time_hint = meta_hints[url]
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                errback=self._handle_detail_error,
                dont_filter=self.full_scan,
                meta={
                    'title_hint': title_hint,
                    'publish_time_hint': publish_time_hint,
                    'shared_state': state
                }
            )

    def _check_next_page(self, state, response_url):
        page = state['page']
        parsed_dates = [d for d in state['dates'] if d is not None]

        if parsed_dates and all(d < self.cutoff_date for d in parsed_dates):
            self.logger.info(f"[{self.name}] All articles on page {page} are older than cutoff {self.cutoff_date}. Stopping pagination.")
            return

        if page < self.MAX_PAGES:
            next_page = page + 1
            next_url = self.BASE_URL.format(page=next_page)
            self.logger.info(f"Continuing to page {next_page}: {next_url}")
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True
            )

    def _handle_detail_error(self, failure):
        self.logger.error(f"Detail request failed: {failure.value}")
        state = failure.request.meta.get('shared_state')
        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state, state['response_url']):
                    yield req

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        state = response.meta.get('shared_state')
        pub_time = item.get('publish_time') if item else None

        if state:
            state['dates'].append(pub_time)

        if item and self.should_process(response.url, pub_time):
            item['author'] = response.css('meta[name="dable:author"]::attr(content)').get() or "東方網"
            item['section'] = "Finance"
            yield item

        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state, response.url):
                    yield req
