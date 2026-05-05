import scrapy
from datetime import datetime
import re
from news_scraper.spiders.smart_spider import SmartSpider

class EsEfeSpider(SmartSpider):
    name = 'es_efe'
    source_timezone = 'Europe/Madrid'

    country_code = 'ESP'

    country = '西班牙'
    language = 'es'
    allowed_domains = ['efe.com']

    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = "div.entry-content, .inside-article, article"

    # 埃菲社板块
    base_url = 'https://efe.com/portada-espana/page/{}/'

    custom_settings = {
        'DOWNLOAD_DELAY': 3.0,
        'CONCURRENT_REQUESTS': 2,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 101,
            'news_scraper.middlewares.BatchDelayMiddleware': 600,
        },
    }

    async def start(self):
        yield scrapy.Request(
            self.base_url.format(1),
            callback=self.parse,
            dont_filter=True,
            meta={'page_idx': 1}
        )

    def parse(self, response):
        self.logger.info(f"PARSE_TRIGGERED: {response.url}, Title: {response.css('title::text').get()}")

        # 1. 提取新闻链接 (基于 WP 结构)
        articles = response.css('h2.entry-title a, article a[href*="/2026-"]')

        current_page = response.meta.get('page_idx', 1)
        has_valid_item_in_window = False

        for art in articles:
            link = art.css('::attr(data-mrf-link)').get() or art.css('::attr(href)').get()
            if not link: continue

            absolute_link = response.urljoin(link)

            # 日期正则检测
            date_match = re.search(r'/(\d{4})-(\d{2})-(\d{2})/', absolute_link)
            if date_match:
                y, m, d = date_match.groups()
                try:
                    pub_time = datetime(year=int(y), month=int(m), day=int(d))
                except: continue

                if not self.should_process(absolute_link, pub_time):
                    continue

                has_valid_item_in_window = True
                yield response.follow(
                    absolute_link,
                    self.parse_detail,
                    meta={'publish_time_hint': pub_time}
                )

        # 翻页
        if has_valid_item_in_window:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page_idx': next_page}
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(response)
        item['author'] = 'EFE News'
        item['section'] = 'España'
        yield item
