import scrapy
import json
from datetime import datetime, timezone
from news_scraper.spiders.smart_spider import SmartSpider

class IqElaphSpider(SmartSpider):
    name = "iq_elaph"
    source_timezone = 'Asia/Baghdad'

    country_code = 'IRQ'
    country = '伊拉克'
    language = 'ar'

    allowed_domains = ["elaph.com", "api.elaph.com"]

    api_url_tmpl = "https://api.elaph.com/v2/web/com/marticles/index/economics/{}"

    use_curl_cffi = False

    fallback_content_selector = '.content-body'

    # Standard browser-like headers for the API request
    api_headers = {
        "Referer": "https://elaph.com/",
        "Origin": "https://elaph.com",
        "Accept": "application/json, text/plain, */*",
    }

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1,
        "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }

    async def start(self):
        yield scrapy.Request(
            self.api_url_tmpl.format(1),
            headers=self.api_headers,
            meta={'page': 1},
            dont_filter=True,
        )

    def parse(self, response):
        if response.status != 200:
            self.logger.error(f"Elaph API returned {response.status}. Body preview: {response.text[:500]}")
            return
        try:
            res_data = json.loads(response.text)
            articles = res_data.get('data', [])
            page = response.meta.get('page', 1)
            self.logger.info(f"Elaph API: Page {page} fetched {len(articles)} items with status {response.status}")
        except Exception as e:
            self.logger.error(f"JSON Parse Error: {e} at {response.url}")
            return

        if not articles:
            return

        has_valid_item_in_window = False
        for art in articles:
            ts = art.get('RelativeTime', 0)
            if not ts:
                continue

            # API returns Unix timestamps (UTC seconds since epoch)
            pub_date = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            pub_date_utc = self.parse_to_utc(pub_date)

            rel_url = art.get('PostingURL')
            if not rel_url:
                continue

            url = f"https://elaph.com{rel_url}"

            if not self.should_process(url, pub_date_utc):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                headers=self.api_headers,
                meta={
                    'publish_time_hint': pub_date_utc,
                    'section_hint': 'Economics',
                },
            )

        if has_valid_item_in_window:
            next_page = page + 1
            yield scrapy.Request(
                self.api_url_tmpl.format(next_page),
                callback=self.parse,
                headers=self.api_headers,
                meta={'page': next_page},
                dont_filter=True,
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class, 'article-title')]/text()",
        )
        item['author'] = "Elaph News"
        item['section'] = "Economics"
        yield item
