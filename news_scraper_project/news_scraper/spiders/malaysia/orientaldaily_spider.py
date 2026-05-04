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
    start_date = "2026-01-01"
    use_curl_cffi = True

    fallback_content_selector = 'article'

    allowed_domains = ["orientaldaily.com.my"]

    # Business section
    BASE_URL = "https://www.orientaldaily.com.my/news/business?page={page}"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 543,
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        },
        'CURLL_CFFI_IMPERSONATE': 'chrome120',
    }

    def start_requests(self):
        yield scrapy.Request(
            self.BASE_URL.format(page=1),
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True,
        )

    def parse_list(self, response):
        page = response.meta['page']

        items = response.css('div.news-item')
        if not items:
            self.logger.info(f"No more items on page {page}")
            return

        self.logger.info(f"Page {page}: found {len(items)} items")
        has_valid_item_in_window = False

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

            has_valid_item_in_window = True

            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                dont_filter=self.full_scan,
                meta={
                    'title_hint': title.strip() if title else None,
                    'publish_time_hint': publish_time,
                }
            )

        # Pagination with circuit breaker
        if has_valid_item_in_window:
            next_page = page + 1
            if next_page <= 1000:  # Safety cap
                yield scrapy.Request(
                    self.BASE_URL.format(page=next_page),
                    callback=self.parse_list,
                    meta={'page': next_page},
                    dont_filter=True,
                )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )

        if not self.should_process(response.url, item.get('publish_time')):
            return

        item['author'] = response.css('meta[name="dable:author"]::attr(content)').get() or "東方網"
        item['section'] = "Finance"

        yield item
