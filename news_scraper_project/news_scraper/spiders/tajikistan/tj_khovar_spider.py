import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider
import re

class TjKhovarSpider(SmartSpider):
    name = 'tj_khovar'
    source_timezone = 'Asia/Dushanbe'

    country_code = 'TJK'

    country = '塔吉克斯坦'
    language = 'tg'
    allowed_domains = ['khovar.tj']
    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = ".shortcode-content"

    MONTH_MAP = {
        'Январ': '01', 'Феврал': '02', 'Март': '03', 'Апрел': '04',
        'Май': '05', 'Июн': '06', 'Июл': '07', 'Август': '08',
        'Сентябр': '09', 'Октябр': '10', 'Ноябр': '11', 'Декабр': '12'
    }

    custom_settings = {
        'CONCURRENT_REQUESTS': 4,
        'ROBOTSTXT_OBEY': False,
    }

    async def start(self):
        yield scrapy.Request('https://khovar.tj/category/economic/', callback=self.parse, dont_filter=True)

    def parse(self, response):
        if self._stop_pagination:
            return

        articles = response.css('h2 a')
        has_valid_item_in_window = False
        for article in articles:
            link = article.css('::attr(href)').get()
            if not link:
                continue

            # Extract date from listing page if available
            publish_time = None
            date_str = article.xpath(
                './ancestor::article[1]//time/@datetime | '
                './ancestor::article[1]//*[contains(@class,"meta")]'
                '/text() | '
                './ancestor::article[1]//*[contains(@class,"date")]'
                '/text()'
            ).get()
            if date_str:
                dt_obj = self._parse_date(date_str.strip())
                if dt_obj:
                    publish_time = self.parse_to_utc(dt_obj)

            if not self.should_process(response.urljoin(link), publish_time):
                continue

            has_valid_item_in_window = True
            yield response.follow(
                link, self.parse_detail,
                meta={"publish_time_hint": publish_time}
            )

        next_page = response.css('a.next.page-numbers::attr(href)').get()
        if has_valid_item_in_window and next_page:
            yield response.follow(next_page, self.parse)

    def parse_detail(self, response):
        title = response.css('h1::text').get('').strip()
        if not title:
            return

        raw_date = response.css('div.author span.meta::text').get('').strip()
        if not raw_date:
            raw_date = response.css('div.author::text').get('').strip()
        dt_obj = self._parse_date(raw_date)
        pub_time = self.parse_to_utc(dt_obj) if dt_obj else None

        if pub_time and not self.should_process(response.url, pub_time):
            self._stop_pagination = True
            return

        item = self.auto_parse_item(response)
        if not item.get('content_plain'):
            paragraphs = response.css('.shortcode-content p::text').getall()
            content = "\n\n".join([p.strip() for p in paragraphs if p.strip()])
            if content:
                item['content_plain'] = content

        author = 'AMIT «Ховар»'
        item['author'] = author
        item['section'] = 'Economic'
        item['title'] = title

        yield item

    def _parse_date(self, date_str):
        if not date_str:
            return None
        for tj_month, en_month in self.MONTH_MAP.items():
            if tj_month in date_str:
                date_str = date_str.replace(tj_month, en_month)
                break
        try:
            return datetime.strptime(date_str, "%m %d, %Y %H:%M")
        except Exception:
            return None
