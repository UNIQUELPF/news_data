import scrapy
from datetime import datetime
import re
import json
from news_scraper.spiders.smart_spider import SmartSpider

class EsElconfidencialSpider(SmartSpider):
    name = 'es_elconfidencial'
    source_timezone = 'Europe/Madrid'

    country_code = 'ESP'

    country = '西班牙'
    language = 'es'
    allowed_domains = ['elconfidencial.com']

    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = "div.news-body, .article-body, article"

    # 实时新闻入口
    base_url = 'https://www.elconfidencial.com/ultima-hora-en-vivo/?page={}'

    custom_settings = {
        'CONCURRENT_REQUESTS': 16,
        'DOWNLOAD_DELAY': 0.5,
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_TIMEOUT': 40
    }

    async def start(self):
        yield scrapy.Request(self.base_url.format(1), callback=self.parse, dont_filter=True)

    def parse(self, response):
        # 1. 提取所有链接，并正则匹配日期指纹: /YYYY-MM-DD/
        all_links = response.css('a::attr(href)').getall()

        current_page = response.meta.get('page', 1)
        has_valid_item_in_window = False

        # 使用 set 去重
        for link in set(all_links):
            # 完整 URL 为: .../2026-03-31/slug/
            date_match = re.search(r'/(\d{4})-(\d{2})-(\d{2})/', link)
            if date_match:
                y, m, d = date_match.groups()
                try:
                    pub_time = datetime(year=int(y), month=int(m), day=int(d))
                except:
                    continue

                if not self.should_process(link, pub_time):
                    continue

                has_valid_item_in_window = True
                yield response.follow(
                    link,
                    self.parse_detail,
                    meta={'publish_time_hint': pub_time}
                )

        # 翻页逻辑
        if has_valid_item_in_window:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(response)
        item['author'] = response.css('span[class*="author"]::text, .signature__name::text').get('El Confidencial').strip()
        item['section'] = 'Última Hora'
        yield item
