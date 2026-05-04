import json
import logging

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

logger = logging.getLogger(__name__)


class WortSpider(SmartSpider):
    """
    Scrapes the Luxemburger Wort (wort.lu) 'neueste' news section.
    Uses Next.js internal API (api/cook/neueste/...) for pagination.
    """
    name = "wort"
    source_timezone = 'Europe/Luxembourg'

    country_code = 'LUX'
    country = '卢森堡'
    language = 'de'

    start_date = "2026-01-01"

    allowed_domains = ["wort.lu"]

    custom_settings = {
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        # Site forces SSO silent login 302s if it detects a standard browser UA on API endpoints.
        'USER_AGENT': "python-requests/2.31.0",
    }

    fallback_content_selector = 'article'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.limit = 30

    def start_requests(self):
        url = f"https://www.wort.lu/api/cook/neueste/?offset=0&count={self.limit}"
        yield scrapy.Request(
            url=url,
            callback=self.parse_api_list,
            cb_kwargs={"offset": 0},
            headers={'Accept': 'application/json'},
            dont_filter=True,
        )

    def parse_api_list(self, response, offset):
        try:
            resp_json = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON on offset {offset}: {e}")
            return

        data = resp_json.get('data', {})
        articles = data.get('mostRecentArticles', {}).get('items', [])

        if not articles:
            self.logger.info(f"Offset {offset} returned empty items list. Stopping.")
            return

        has_valid_item_in_window = False

        for record in articles:
            href = record.get('href')
            pub_date_str = record.get('published') or record.get('updated')

            if not href or not pub_date_str:
                continue

            publish_time = self.parse_date(pub_date_str)
            if not publish_time:
                continue

            detail_url = f"https://www.wort.lu{href}" if href.startswith('/') else href

            if not self.should_process(detail_url, publish_time):
                continue

            has_valid_item_in_window = True

            title = record.get('title') or record.get('teaserHeadline') or ""
            section_data = record.get('homeSection')
            section = section_data.get('name') if isinstance(section_data, dict) else "neueste"
            authors = ", ".join(
                [a.get('name', '') for a in record.get('authors', [])
                 if isinstance(a, dict) and a.get('name')]
            )

            yield scrapy.Request(
                url=detail_url,
                callback=self.parse_detail,
                meta={
                    "title_hint": title,
                    "publish_time_hint": publish_time,
                    "section_hint": section,
                    "author_hint": authors if authors else "Luxemburger Wort",
                },
                dont_filter=self.full_scan,
            )

        # Pagination: continue if we found valid items and the page was full
        if has_valid_item_in_window and len(articles) == self.limit:
            next_offset = offset + self.limit
            next_url = (
                f"https://www.wort.lu/api/cook/neueste/"
                f"?offset={next_offset}&count={self.limit}"
            )
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_api_list,
                cb_kwargs={"offset": next_offset},
                headers={'Accept': 'application/json'},
                dont_filter=True,
            )
        else:
            self.logger.info(
                f"Reached cutoff or end of list at offset {offset}. Stopping."
            )

    def parse_detail(self, response):
        """Parse article detail page using standardized SmartSpider extraction."""
        item = self.auto_parse_item(response)

        # Override author with listing page metadata (more reliable than page extraction)
        author_hint = response.meta.get("author_hint")
        if author_hint:
            item['author'] = author_hint

        yield item
