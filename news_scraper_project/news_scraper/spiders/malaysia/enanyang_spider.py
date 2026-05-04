import json
import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class EnanyangSpider(SmartSpider):
    name = "malaysia_enanyang"

    country_code = "MYS"
    country = "马来西亚"
    language = "zh"
    source_timezone = "Asia/Kuala_Lumpur"
    start_date = "2026-01-01"
    allowed_domains = ["enanyang.my"]

    fallback_content_selector = "div[class*='article-page-post-content']"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.5,
    }

    # cat=2 corresponds to 财经 (Finance)
    CATEGORIES = [
        {'id': 2, 'name': 'Finance'}
    ]

    async def start(self):
        for cat in self.CATEGORIES:
            url = f"https://www.enanyang.my/api/category-posts?cat={cat['id']}&offset=0&pagenum=1&excludeids="
            yield scrapy.Request(url, callback=self.parse_list, meta={'cat': cat, 'page': 1}, dont_filter=True)

    def parse_list(self, response):
        cat = response.meta['cat']
        page = response.meta['page']

        try:
            items = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
            return

        if not items or not isinstance(items, list):
            self.logger.info(f"No items found on page {page} for category {cat['name']}")
            return

        self.logger.info(f"Page {page} for {cat['name']}: found {len(items)} items")

        has_valid_item_in_window = False

        for item in items:
            url = item.get('permalink')
            title = item.get('title')
            pub_date_str = item.get('post_date')

            if not url or not pub_date_str:
                continue

            publish_time = self.parse_date(pub_date_str)

            if not self.should_process(url, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    'title_hint': title,
                    'publish_time_hint': publish_time,
                    'section_hint': cat['name'],
                }
            )

        if has_valid_item_in_window:
            next_page = page + 1
            next_url = f"https://www.enanyang.my/api/category-posts?cat={cat['id']}&offset=0&pagenum={next_page}&excludeids="
            yield scrapy.Request(next_url, callback=self.parse_list, meta={'cat': cat, 'page': next_page}, dont_filter=True)

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class,'entry-title')]/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )

        item['author'] = "e南洋"
        item['section'] = response.meta.get('section_hint', 'Finance')

        yield item
