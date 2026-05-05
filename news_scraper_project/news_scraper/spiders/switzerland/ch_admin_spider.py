import scrapy
import json
from news_scraper.spiders.smart_spider import SmartSpider

class ChAdminSpider(SmartSpider):
    name = 'ch_admin'
    source_timezone = 'Europe/Zurich'

    country_code = 'CHE'
    country = '瑞士'
    language = 'en'
    allowed_domains = ['news.admin.ch', 'admin.ch', 'www.news.admin.ch']

    use_curl_cffi = True
    strict_date_required = True
    fallback_content_selector = "main"

    custom_settings = {
        'DEFAULT_REQUEST_HEADERS': {
            'Origin': 'https://www.news.admin.ch',
            'Referer': 'https://www.news.admin.ch/',
            'Accept': 'application/json, text/plain, */*',
        }
    }

    async def start(self):
        self.base_api = "https://d-nsbc-p.admin.ch/v1/search"
        params = (
            "languages=en"
            "&newsKinds=CONTENT_HUB"
            "&newsKinds=ONSB"
            "&start_date=2026-01-01T00:00:00.000Z"
            "&end_date=2026-12-31T23:59:59.999Z"
            "&limit=12"
            "&sort=DESC"
        )
        url = f"{self.base_api}?{params}&offset=0"
        yield scrapy.Request(url=url, callback=self.parse_api)

    def parse_api(self, response):
        try:
            data = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
            return

        items_list = data.get('items', [])
        if not items_list:
            return

        has_valid_item_in_window = False

        for entry in items_list:
            article_id = entry.get('id')
            url = entry.get('externalUrl')
            if not url:
                url = f"https://www.news.admin.ch/en/newnsb/{article_id}"

            # Date extraction from API response
            pub_date = None
            pub_date_str = entry.get('publishDate', '')
            if pub_date_str:
                pub_date = self.parse_date(pub_date_str)

            if not self.should_process(url, pub_date):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_article,
                meta={
                    'entry': entry,
                    'publish_time_hint': pub_date,
                    'title_hint': entry.get('title'),
                },
                dont_filter=True
            )

        # Pagination via API offset
        if has_valid_item_in_window:
            current_offset = int(response.url.split('offset=')[1].split('&')[0])
            next_offset = current_offset + 12
            next_url = response.url.replace(f"offset={current_offset}", f"offset={next_offset}")
            yield scrapy.Request(next_url, callback=self.parse_api)

    def parse_article(self, response):
        entry = response.meta.get('entry', {})

        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content"
        )

        # Override/Set specific fields
        item['author'] = 'Swiss Federal News Service'
        item['section'] = 'Federal Government'

        # Content fallback: if ContentEngine didn't capture enough, use API description
        if not item.get('content_plain') or len(item['content_plain']) < 5:
            desc = entry.get('content', {}).get('metadata', {}).get('description')
            if desc:
                item['content_plain'] = desc
                if not item.get('content_html'):
                    item['content_html'] = f"<p>{desc}</p>"

        if item.get('title') or (item.get('content_plain') and len(item['content_plain']) > 5):
            yield item
