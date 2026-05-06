import logging

import scrapy
from bs4 import BeautifulSoup

from news_scraper.spiders.smart_spider import SmartSpider

logger = logging.getLogger(__name__)


class Lebanon24Spider(SmartSpider):
    name = "lebanon24"

    country_code = "LBN"
    country = "黎巴嫩"
    language = "ar"
    source_timezone = "Asia/Beirut"
    start_date = "2026-01-01"

    allowed_domains = ["lebanon24.com"]

    # Content locked behind login wall; no detail page extraction needed
    fallback_content_selector = None

    # Stop pagination when date extraction fails on listing page
    strict_date_required = True

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.categories = [
            (
                "https://www.lebanon24.com/section/5/%D8%A5%D9%82%D8%AA%D8%B5%D8%A7%D8%AF",
                "5",
            )
        ]

    async def start(self):
        for main_url, cat_id in self.categories:
            yield scrapy.Request(
                url=main_url,
                callback=self.parse_first_page,
                cb_kwargs={"cat_id": cat_id, "load_index": 1},
                dont_filter=True,
            )

    def parse_first_page(self, response, cat_id, load_index):
        if self._stop_pagination:
            return
        has_valid_item_in_window = False
        for item in self._parse_list(response):
            has_valid_item_in_window = True
            yield item

        if has_valid_item_in_window:
            next_url = (
                f"https://www.lebanon24.com/Website/DynamicPages/LoadMore/"
                f"Loadmore_DocumentCategory.aspx?loadindex={load_index}&lang=ar&ID={cat_id}"
            )
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_list_page,
                cb_kwargs={"cat_id": cat_id, "load_index": load_index},
                dont_filter=True,
            )

    def parse_list_page(self, response, cat_id, load_index):
        if self._stop_pagination:
            return
        has_valid_item_in_window = False
        for item in self._parse_list(response):
            has_valid_item_in_window = True
            yield item

        if has_valid_item_in_window:
            next_index = load_index + 1
            next_url = (
                f"https://www.lebanon24.com/Website/DynamicPages/LoadMore/"
                f"Loadmore_DocumentCategory.aspx?loadindex={next_index}&lang=ar&ID={cat_id}"
            )
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_list_page,
                cb_kwargs={"cat_id": cat_id, "load_index": next_index},
                dont_filter=True,
            )
        else:
            logger.info(
                f"Stopping pagination for category {cat_id} at index "
                f"{load_index} (hit cutoff or empty)."
            )

    def _parse_list(self, response):
        """Parse article blocks from the list/LoadMore HTML and yield V2 dict items."""
        soup = BeautifulSoup(response.text, "html.parser")
        article_links = soup.select('a[href*="/news/"]')
        seen_urls = set()

        for a_tag in article_links:
            href = a_tag.get("href")
            if not href:
                continue

            url = response.urljoin(href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = a_tag.text.strip()
            if not title:
                continue

            # Walk up ancestors to find the date in .CardsControls-Date
            wrapper = a_tag.find_parent("div")
            date_tag = None
            while wrapper:
                if len(wrapper.select('a[href*="/news/"]')) > 5:
                    break
                date_tag = wrapper.select_one(".CardsControls-Date")
                if date_tag:
                    break
                wrapper = wrapper.find_parent("div")

            pub_time = None
            if date_tag:
                date_text = date_tag.text.strip()
                # Format: "01:48 | 2026-03-24" (Beirut local time)
                try:
                    if "|" in date_text:
                        time_part, date_part = date_text.split("|")
                        dt_string = f"{date_part.strip()} {time_part.strip()}"
                        pub_time = self.parse_date(dt_string)
                    else:
                        pub_time = self.parse_date(date_text)
                except Exception as e:
                    logger.debug(f"Failed to parse date '{date_text}': {e}")

            if not self.should_process(url, pub_time):
                self._stop_pagination = True
                continue

            yield {
                "url": url,
                "title": title,
                "raw_html": "",
                "content": "",
                "content_cleaned": "",
                "content_markdown": "",
                "content_plain": "",
                "images": [],
                "publish_time": pub_time,
                "author": "Lebanon24",
                "language": self.language,
                "section": "Economy",
                "country_code": self.country_code,
                "country": self.country,
            }
