import scrapy
import json
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class ThNationthailandSpider(SmartSpider):
    name = "th_nationthailand"
    source_timezone = 'Asia/Bangkok'
    country_code = 'THA'
    country = '泰国'
    language = 'en'

    allowed_domains = ['nationthailand.com', 'api.nationthailand.com']

    base_api_url = 'https://api.nationthailand.com/api/v1.0/categories/news?page={}'

    use_curl_cffi = True
    fallback_content_selector = ".detail"
    strict_date_required = True

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1
    }

    async def start(self):
        yield scrapy.Request(
            self.base_api_url.format(1),
            callback=self.parse,
            meta={'page': 1}
        )

    def parse(self, response):
        try:
            data = json.loads(response.text)
            items = data.get('data', [])
        except Exception as e:
            self.logger.error(f"Failed to parse JSON API: {e}")
            return

        if not items:
            self.logger.info("No more items found in API response.")
            return

        has_valid_item_in_window = False

        for item in items:
            path = item.get('link')
            if not path:
                continue

            article_url = f"https://www.nationthailand.com{path}" if path.startswith('/') else path

            # Try to extract date from API item for circuit breaker
            pub_time = None
            date_str = item.get('publishDate') or item.get('publishedAt') or item.get('createdAt')
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    pub_time = self.parse_to_utc(dt)
                except Exception:
                    pass

            if pub_time is not None:
                if not self.should_process(article_url, pub_time):
                    continue
                has_valid_item_in_window = True
            else:
                # No date from API; pass through for detail-level filtering
                has_valid_item_in_window = True

            meta = {'page': response.meta.get('page', 1)}
            if pub_time:
                meta['publish_time_hint'] = pub_time
            yield scrapy.Request(article_url, self.parse_article, meta=meta)

        # Pagination with circuit breaker
        if has_valid_item_in_window:
            current_page = response.meta.get('page', 1)
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_api_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        item = self.auto_parse_item(response)

        if not self.should_process(response.url, item.get('publish_time')):
            return

        item['author'] = response.css('meta[name="author"]::attr(content)').get() or 'Nation Thailand'
        item['section'] = 'News'

        yield item
