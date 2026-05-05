import scrapy
from datetime import datetime
import json
from urllib.parse import quote
from news_scraper.spiders.smart_spider import SmartSpider


class SgChannelNewsAsiaSpider(SmartSpider):
    name = 'sg_channelnewsasia'
    country_code = 'SGP'
    country = '新加坡'
    language = 'en'
    source_timezone = 'Asia/Singapore'
    start_date = '2024-01-01'
    allowed_domains = ['channelnewsasia.com', 'algolianet.com', 'algolia.net']
    fallback_content_selector = '.text-long'

    algolia_app_id = 'KKWFBQ38XF'
    algolia_api_key = 'e4b61225b5a00162761c501328a58ac7'
    algolia_index = 'cnarevamp-ezrqv5hx'

    use_curl_cffi = True

    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 543,
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        },
        'CURLL_CFFI_IMPERSONATE': 'chrome120',
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 2
    }

    def start_requests(self):
        yield self.get_algolia_request(0)

    def get_algolia_request(self, page_num):
        # 使用更为稳健的 URL 参数编码方式，规避 POST 中的 400 冲突
        params = f'facetFilters=[["type:article"]]&hitsPerPage=30&page={page_num}'
        # 完整的 Algolia REST GET 端点 (Search Only)
        url = f'https://{self.algolia_app_id}-dsn.algolia.net/1/indexes/{self.algolia_index}?x-algolia-application-id={self.algolia_app_id}&x-algolia-api-key={self.algolia_api_key}&{params}'

        return scrapy.Request(
            url,
            method='GET',
            callback=self.parse,
            meta={'page': page_num},
            dont_filter=True
        )

    def parse(self, response):
        try:
            data = json.loads(response.text)
            hits = data.get('hits', [])
            self.logger.info(f"Algolia GET API: Found {len(hits)} hits on page {response.meta.get('page', 0)}")
        except Exception as e:
            self.logger.error(f"Failed to parse Algolia JSON: {e}")
            return

        current_page = response.meta.get('page', 0)
        valid_count = 0

        for hit in hits:
            href = hit.get('link_absolute')
            ts = hit.get('field_release_date')

            if href and ts:
                pub_date = datetime.fromtimestamp(int(ts))
                # V2: 使用 should_process 替代 filter_date
                if self.should_process(href, pub_date):
                    valid_count += 1
                    yield scrapy.Request(href, self.parse_article, meta={'publish_time_hint': pub_date})

        if valid_count > 0 and current_page < 1000:
            yield self.get_algolia_request(current_page + 1)

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
        )
        item['author'] = 'Channel News Asia'
        item['section'] = response.url.split('/')[3] if len(response.url.split('/')) > 3 else 'Unknown'
        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
