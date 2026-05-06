import json
from datetime import datetime

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class TheEdgeSpider(SmartSpider):
    name = "malaysia_theedge"

    country_code = "MYS"
    country = "马来西亚"
    language = "en"
    source_timezone = "Asia/Kuala_Lumpur"
    start_date = "2026-01-01"
    allowed_domains = ["theedgemalaysia.com"]

    use_curl_cffi = True
    fallback_content_selector = "[class*=\"newsdetailsContent\"]"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.5,
    }

    # Categories to scrape
    CATEGORIES = [
        {'id': 'economy', 'name': 'Economy'}
    ]

    def start_requests(self):
        for cat in self.CATEGORIES:
            url = f"https://theedgemalaysia.com/api/loadMoreCategories?offset=0&categories={cat['id']}"
            yield scrapy.Request(
                url,
                callback=self.parse_list,
                meta={'cat': cat, 'offset': 0},
                dont_filter=True
            )

    def parse_list(self, response):
        cat = response.meta['cat']
        offset = response.meta['offset']

        try:
            data = json.loads(response.text)
            items = data.get('results', [])
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
            return

        if not items:
            self.logger.info(f"No items found for offset {offset} in category {cat['name']}")
            return

        self.logger.info(f"Offset {offset} for {cat['name']}: found {len(items)} items")

        has_valid_item_in_window = False

        for item in items:
            title = item.get('title')
            nid = item.get('nid')
            permalink = item.get('permalink')
            if not permalink and nid:
                permalink = f"/node/{nid}"

            if not permalink:
                continue

            url = f"https://theedgemalaysia.com{permalink}"

            # Timestamp is in milliseconds (Unix timestamp, always UTC)
            created_ms = item.get('created')
            if not created_ms:
                continue

            if created_ms > 10**11:
                dt = datetime.utcfromtimestamp(created_ms / 1000)
            else:
                dt = datetime.utcfromtimestamp(created_ms)

            if not self.should_process(url, dt):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    'title_hint': title,
                    'publish_time_hint': dt,
                    'section_hint': cat['name']
                }
            )

        if has_valid_item_in_window:
            next_offset = offset + 10
            next_url = f"https://theedgemalaysia.com/api/loadMoreCategories?offset={next_offset}&categories={cat['id']}"
            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={'cat': cat, 'offset': next_offset},
                dont_filter=True
            )
        else:
            self.logger.info(f"No valid items in window for {cat['name']} at offset {offset}, stopping pagination")

    def parse_detail(self, response):
        item = self.auto_parse_item(response)

        # Try to extract author from meta tag or page structure
        author = (
            response.css('meta[name="author"]::attr(content)').get() or
            response.css('[class*="news-detail_authorName"]::text').get() or
            ""
        )
        item['author'] = author.strip()

        yield item
