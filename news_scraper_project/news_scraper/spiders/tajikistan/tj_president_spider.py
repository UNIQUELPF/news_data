import scrapy
import json
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class TjPresidentSpider(SmartSpider):
    name = 'tj_president'
    source_timezone = 'Asia/Dushanbe'

    country_code = 'TJK'

    country = '塔吉克斯坦'
    language = 'en'
    allowed_domains = ['president.tj', 'controlpanel.president.tj']
    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = None

    base_list_url = 'https://controlpanel.president.tj/api/home-event?event_type=news&lang_id=3&page={}'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._requested_pages = set()

    async def start(self):
        yield scrapy.Request(self.base_list_url.format(1), callback=self.parse, meta={'page': 1})

    def parse(self, response):
        try:
            data = json.loads(response.text)
            items = data.get('data', [])
        except Exception as e:
            self.logger.error(f"Failed to parse List JSON: {e}")
            return

        if not items:
            self.logger.info("No more items found on this page.")
            return

        current_page = response.meta.get('page', 1)
        has_valid_item_in_window = False

        for item in items:
            news_id = item.get('id')
            if news_id:
                detail_url = f'https://controlpanel.president.tj/api/event/show?type=news&id={news_id}&lang_id=3'
                has_valid_item_in_window = True
                yield scrapy.Request(detail_url, self.parse_detail, meta={'news_id': news_id})

        # Request next page; stopped by _stop_pagination when items are too old
        next_page = current_page + 1
        if (next_page not in self._requested_pages
                and not self._stop_pagination):
            self._requested_pages.add(next_page)
            yield scrapy.Request(
                self.base_list_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_detail(self, response):
        try:
            json_data = json.loads(response.text)
            detail = json_data.get('data', {})
        except Exception as e:
            self.logger.error(f"Failed to parse Detail JSON: {e}")
            return

        title = detail.get('title', '').strip()
        pub_date_str = detail.get('publish_date', '')

        pub_time = None
        if pub_date_str:
            try:
                dt_obj = datetime.strptime(pub_date_str, "%Y-%m-%d %H:%M:%S")
                pub_time = self.parse_to_utc(dt_obj)
            except Exception:
                pass

        if not self.should_process(response.url, pub_time):
            self._stop_pagination = True
            return

        content = detail.get('text', '').strip()

        item = {
            'url': f"https://www.president.tj/event/news/{response.meta.get('news_id')}",
            'title': title,
            'content': content,
            'raw_html': response.text,
            'publish_time': pub_time,
            'author': 'President.tj',
            'language': self.language,
            'section': 'News',
            'country_code': self.country_code,
            'country': self.country,
        }

        yield item
