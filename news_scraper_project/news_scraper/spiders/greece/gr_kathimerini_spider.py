# 希腊Kathimerini爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class GrKathimeriniSpider(SmartSpider):
    name = 'gr_kathimerini'

    country_code = 'GRC'
    country = '希腊'
    language = 'el'
    source_timezone = 'Europe/Athens'
    use_curl_cffi = True

    start_date = '2026-04-01'
    fallback_content_selector = 'main.container, .entry-content'

    allowed_domains = ['kathimerini.gr']

    # 航运报经济板块
    base_url = 'https://www.kathimerini.gr/economy/local/page/{}/'
    start_urls = [base_url.format(1)]

    custom_settings = {
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 500,
        }
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_list, dont_filter=True, meta={'page': 1})

    def parse_list(self, response):
        cards = response.css('div.card')
        if not cards:
            return

        has_valid_item_in_window = False

        for card in cards:
            link = card.css('a::attr(href)').get()
            date_str = card.css('.card-date::text').get()

            if not link or not date_str:
                continue

            # Parse list-page date (format: 31.03.2026)
            try:
                date_clean = date_str.strip()
                day, month, year = date_clean.split('.')
                list_date = datetime(year=int(year), month=int(month), day=int(day))
            except Exception:
                continue

            publish_time = self.parse_date(date_str)
            full_url = response.urljoin(link)

            if not self.should_process(full_url, publish_time):
                continue

            self.logger.info(f"Processing: {link} ({date_str})")
            has_valid_item_in_window = True

            yield scrapy.Request(
                full_url,
                callback=self.parse_detail,
                dont_filter=True,
                meta={'publish_time_hint': publish_time}
            )

        # Pagination with circuit breaker
        if has_valid_item_in_window:
            current_page = response.meta.get('page', 1)
            next_page = current_page + 1
            next_url = self.base_url.format(next_page)
            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                dont_filter=True,
                meta={'page': next_page}
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content"
        )

        if not self.should_process(response.url, item.get('publish_time')):
            return

        item['author'] = 'Kathimerini Economy'
        item['section'] = 'Economy/Local'

        yield item
