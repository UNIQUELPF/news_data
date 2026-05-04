import html
import json
import re

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class GouvernementSpider(SmartSpider):
    name = "luxembourg_gouvernement"

    country_code = 'LUX'
    country = '卢森堡'
    language = 'fr'
    source_timezone = 'Europe/Luxembourg'

    allowed_domains = ["gouvernement.lu"]
    fallback_content_selector = "div.cmp-text"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.5,
    }

    base_url = (
        "https://gouvernement.lu/content/gouvernement2024/fr/actualites/"
        "toutes_actualites/jcr:content/root/root-responsivegrid/"
        "content-responsivegrid/sections-responsivegrid/section/col1/"
        "search.searchresults-content.html?format=json&page={}"
    )

    def start_requests(self):
        yield scrapy.Request(
            self.base_url.format(1),
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True
        )

    def parse_list(self, response):
        page = response.meta['page']

        match = re.search(r'data-json=\"(.*?)\"', response.text, re.DOTALL)
        if not match:
            self.logger.error(f"Failed to find data-json on {response.url}")
            return

        try:
            encoded_json = match.group(1)
            decoded_json = html.unescape(encoded_json)
            data = json.loads(decoded_json)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
            return

        items = data.get('search', {}).get('items', [])
        if not items:
            self.logger.info(f"No items found on page {page}")
            return

        self.logger.info(f"Page {page}: found {len(items)} items")

        has_valid_item_in_window = False

        for item in items:
            page_data = item.get('page', {})
            title = page_data.get('title')
            url_rel = item.get('url')

            # Parse publish time (format: YYYY/MM/DD HH:MM:SS in Europe/Luxembourg)
            metadata = item.get('hitMetaData', {})
            pub_date_str = metadata.get('first_release_date_hour') or item.get('first_release_date_hour')

            if not pub_date_str:
                pub_date_str = item.get('startDateFormating', {}).get('fulltimeString')

            if not pub_date_str:
                self.logger.warning(f"Item missing publish date: {title}")
                continue

            publish_time = self.parse_date(pub_date_str)
            if not publish_time:
                self.logger.warning(f"Failed to parse date '{pub_date_str}': {title}")
                continue

            # Build full URL
            full_url = url_rel
            if full_url.startswith('//'):
                full_url = 'https:' + full_url
            elif full_url.startswith('/'):
                full_url = 'https://gouvernement.lu' + full_url

            if not self.should_process(full_url, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
                meta={
                    'title_hint': title,
                    'publish_time_hint': publish_time,
                    'section_hint': item.get('third_level', 'news'),
                }
            )

        if has_valid_item_in_window:
            next_page = page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True
            )
        else:
            self.logger.info(f"Reached cutoff or end of content at page {page}")

    def parse_article(self, response):
        item = self.auto_parse_item(response)
        item['author'] = ''
        yield item
