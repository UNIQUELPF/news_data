import scrapy
from datetime import datetime
import json
from news_scraper.spiders.smart_spider import SmartSpider


class SgBusinessTimesSpider(SmartSpider):
    name = 'sg_businesstimes'
    country_code = 'SGP'
    country = '新加坡'
    language = 'en'
    source_timezone = 'Asia/Singapore'
    start_date = '2024-01-01'
    allowed_domains = ['businesstimes.com.sg']
    fallback_content_selector = '.font-lucida'

    # 商业时报隐藏的分页 API (v1)
    api_url = 'https://www.businesstimes.com.sg/_plat/api/v1/articles/sections?size=20&sections=singapore_economy-policy&page={}'
    start_urls = [api_url.format(1)]

    use_curl_cffi = True

    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 543,
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        },
        'CURLL_CFFI_IMPERSONATE': 'chrome120',
        'DEFAULT_REQUEST_HEADERS': {
            'referer': 'https://www.businesstimes.com.sg/singapore/economy-policy',
            'x-requested-with': 'XMLHttpRequest'
        },
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 2
    }

    def parse(self, response):
        try:
            data = json.loads(response.text)
            items = data.get('data', {}).get('items', [])
            self.logger.info(f"API (v1) Response: Found {len(items)} items on page {response.meta.get('page', 1)}")
        except Exception as e:
            self.logger.error(f"Failed to parse API JSON on {response.url}: {e}")
            return

        if not items:
            self.logger.info("No more items found in API response.")
            return

        current_page = response.meta.get('page', 1)
        valid_items = 0

        for item in items:
            article_data = item.get('articleData', {})
            href = article_data.get('urlPath')
            # 使用 ISO 格式的 publishTime: 2026-03-20T02:30:00.000Z
            pub_time_raw = article_data.get('publishTime')

            if not href or not pub_time_raw:
                continue

            try:
                pub_date = datetime.fromisoformat(pub_time_raw.replace('Z', '+00:00'))
            except:
                continue

            # Make naive for SmartSpider comparison (earliest_date is naive)
            if pub_date.tzinfo:
                pub_date = pub_date.replace(tzinfo=None)

            if self.should_process(href, pub_date):
                valid_items += 1
                yield response.follow(
                    href,
                    self.parse_article,
                    meta={'publish_time_hint': pub_date}
                )

        # 翻页推进
        if valid_items > 0 and current_page < 1000:
            next_page = current_page + 1
            yield scrapy.Request(
                self.api_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
        )
        item['author'] = 'Business Times SG'
        item['section'] = 'Economy & Policy'
        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
