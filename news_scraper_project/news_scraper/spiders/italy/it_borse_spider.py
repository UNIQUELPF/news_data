import scrapy
import re
import dateparser
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class ItBorseSpider(SmartSpider):
    name = "it_borse"

    source_timezone = 'Europe/Rome'

    country_code = 'ITA'
    country = '意大利'
    language = 'it'
    start_date = '2024-01-01'

    # Italian date format: "15 aprile 2026"
    dateparser_settings = {
        'DATE_ORDER': 'DMY',
    }

    # Italian month names for fallback manual parsing
    _MESE_MAP = {
        'gennaio': '01', 'febbraio': '02', 'marzo': '03', 'aprile': '04',
        'maggio': '05', 'giugno': '06', 'luglio': '07', 'agosto': '08',
        'settembre': '09', 'ottobre': '10', 'novembre': '11', 'dicembre': '12',
    }

    allowed_domains = ["borse.it"]

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
    }

    use_curl_cffi = True

    fallback_content_selector = 'article.single-post__article'

    def start_requests(self):
        yield scrapy.Request(
            "https://www.borse.it/notizie",
            callback=self.parse,
            dont_filter=True,
        )

    def parse(self, response):
        """Parse listing page: https://www.borse.it/notizie"""
        # Each article card contains a link with class card-post__title
        article_links = response.css('a.card-post__title::attr(href)').getall()
        if not article_links:
            self.logger.warning(f"No article links found on {response.url}")
            return

        has_valid_item_in_window = False

        for link in article_links:
            if not link.startswith('http'):
                link = response.urljoin(link)

            # Extract date from the list page for early filtering
            publish_time = self._extract_listing_date(response, link)

            if not publish_time:
                self.logger.error(
                    f"STRICT STOP: No date found for {link}. Terminating spider."
                )
                return

            if not self.should_process(link, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                link,
                callback=self.parse_detail,
                meta={
                    "publish_time_hint": publish_time,
                },
                dont_filter=self.full_scan,
            )

        # Pagination: follow "next" link if we saw valid items in this window
        if has_valid_item_in_window:
            next_page = response.css('a.next.page-numbers::attr(href)').get()
            if next_page:
                yield scrapy.Request(
                    response.urljoin(next_page),
                    callback=self.parse,
                    dont_filter=True,
                )

    def _extract_listing_date(self, response, article_link):
        """
        Extract date from the listing page for a given article link.
        Tries multiple selectors and falls back to textual Italian date parsing.
        """
        # Strategy 1: Find the article card containing this link and extract
        # any <time> element with datetime attribute
        card = response.xpath(
            f'//a[contains(@class,"card-post__title") and @href="{article_link}"]'
            '/ancestor::*[contains(@class,"card-post") or contains(@class,"card")][1]'
        )
        if not card:
            card = response.xpath(
                f'//a[contains(@class,"card-post__title") and @href="{article_link}"]'
                '/ancestor::article[1]'
            )
        if not card:
            card = response.xpath(
                f'//a[contains(@class,"card-post__title") and @href="{article_link}"]'
                '/ancestor::div[contains(@class,"post") or contains(@class,"card")][1]'
            )

        if card:
            # Try <time datetime="...">
            time_attr = card.css('time::attr(datetime)').get()
            if time_attr:
                parsed = dateparser.parse(time_attr, settings=self.dateparser_settings)
                if parsed:
                    return self.parse_to_utc(parsed)

            # Try span.date (same as detail page)
            date_text = card.css('span.date::text').get()
            if date_text:
                parsed = self._parse_italian_date(date_text.strip())
                if parsed:
                    return parsed

            # Try any element that looks like an Italian date
            all_texts = card.css('*::text').getall()
            for text in all_texts:
                text = text.strip()
                if self._looks_like_italian_date(text):
                    parsed = self._parse_italian_date(text)
                    if parsed:
                        return parsed

        # Strategy 2: Try dateparser on the card's full text as a last resort
        if card:
            card_text = ' '.join(card.css('*::text').getall())
            if card_text:
                parsed = dateparser.parse(
                    card_text,
                    settings=self.dateparser_settings,
                    languages=['it'],
                )
                if parsed:
                    return self.parse_to_utc(parsed)

        return None

    def _looks_like_italian_date(self, text):
        """Check if text looks like an Italian date string."""
        if not text:
            return False
        # Pattern: "DD mese YYYY" or "DD mese YY"
        pattern = r'\d{1,2}\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{2,4}'
        return bool(re.search(pattern, text.lower()))

    def _parse_italian_date(self, date_str):
        """
        Parse Italian date strings like '15 aprile 2026'.
        First tries dateparser, then falls back to manual parsing.
        """
        if not date_str:
            return None
        date_str = date_str.strip().lower()

        # Try dateparser first
        parsed = dateparser.parse(
            date_str,
            settings=self.dateparser_settings,
            languages=['it'],
        )
        if parsed:
            return self.parse_to_utc(parsed)

        # Fallback: manual parsing using month map
        try:
            parts = date_str.split()
            if len(parts) >= 3:
                day = int(re.sub(r'\D', '', parts[0]))
                month_str = parts[1]
                month = int(self._MESE_MAP.get(month_str, '01'))
                year = int(re.sub(r'\D', '', parts[2]))
                if 1000 <= year <= 2100 and 1 <= day <= 31:
                    dt_obj = datetime(year, month, day)
                    return self.parse_to_utc(dt_obj)
        except (ValueError, IndexError):
            pass

        return None

    def parse_detail(self, response):
        """Parse article detail page using SmartSpider auto_parse_item."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//span[@class='date']/text()",
        )

        item['author'] = "Borse.it"
        item['section'] = "Notizie"

        yield item
