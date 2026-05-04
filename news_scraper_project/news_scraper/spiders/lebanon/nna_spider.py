import json
from datetime import datetime

import scrapy
from bs4 import BeautifulSoup

from news_scraper.spiders.smart_spider import SmartSpider


class LebanonNnaSpider(SmartSpider):
    """
    Spider for National News Agency - Lebanon (nna-leb.gov.lb).
    Uses the backend API endpoint for lists and details.
    Supports full scan and incremental mode.
    """
    name = "lebanon_nna"

    country_code = 'LBN'
    country = '黎巴嫩'
    language = 'ar'
    source_timezone = 'Asia/Beirut'
    start_date = '2024-01-01'

    allowed_domains = ["nna-leb.gov.lb"]

    # The API provides reliable unix timestamps for every article
    strict_date_required = True

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "DOWNLOAD_FAIL_ON_DATALOSS": False
    }

    def start_requests(self):
        yield scrapy.Request(
            "https://backend.nna-leb.gov.lb/api/ar/news/latest?category_id=4&page=1",
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True
        )

    def parse_list(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse JSON on {response.url}")
            return

        news_list = data.get("data", {}).get("news", [])
        if not news_list:
            self.logger.info("No news items found in JSON.")
            return

        self.logger.info(f"Loaded page with {len(news_list)} news items. URL: {response.url}")

        has_valid_item_in_window = False

        for item in news_list:
            # publish_date is standard unix timestamp in this API
            pub_time_unix = item.get("publish_date")
            if pub_time_unix:
                pub_time = datetime.utcfromtimestamp(pub_time_unix)
            else:
                pub_time = None

            article_id = item.get("id")
            title = item.get("title", "No Title")
            url = item.get("url", f"https://nna-leb.gov.lb/ar/news/short/{article_id}")
            url = url.replace('\\/', '/')

            if not self.should_process(url, pub_time):
                continue

            has_valid_item_in_window = True

            detail_url = f"https://backend.nna-leb.gov.lb/api/ar/news/{article_id}"

            yield scrapy.Request(
                detail_url,
                callback=self.parse_article,
                meta={
                    'title_hint': title,
                    'publish_time_hint': pub_time,
                    'article_url': url,
                    'section_hint': 'Economy',
                },
            )

        if has_valid_item_in_window:
            pagination = data.get("data", {}).get("pagination", {})
            current_page = pagination.get("current_page", 1)
            last_page = pagination.get("last_page", 1)

            if current_page < last_page:
                next_page = current_page + 1
                next_url = f"https://backend.nna-leb.gov.lb/api/ar/news/latest?category_id=4&page={next_page}"
                self.logger.info(f"Paginating to page {next_page}")
                yield scrapy.Request(next_url, callback=self.parse_list, dont_filter=True)

    def parse_article(self, response):
        meta = response.meta

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse article JSON on {response.url}")
            return

        article_data = data.get("data", {})

        content_html = article_data.get("content", "")
        if content_html:
            soup = BeautifulSoup(content_html, "html.parser")
            content_plain = soup.get_text(separator="\n", strip=True)
        else:
            content_plain = ""

        # Build V2 item dict compatible with unified articles table
        item = {
            "url": meta.get('article_url', response.url),
            "title": meta.get('title_hint', "No Title"),
            "content_plain": content_plain,
            "content": content_plain,
            "content_cleaned": content_plain,
            "content_markdown": content_plain,
            "raw_html": content_html,
            "publish_time": meta.get('publish_time_hint'),
            "author": "NNA Lebanon",
            "language": self.language,
            "section": meta.get('section_hint', 'Economy'),
            "country_code": self.country_code,
            "country": self.country,
            "images": [],
        }
        yield item
