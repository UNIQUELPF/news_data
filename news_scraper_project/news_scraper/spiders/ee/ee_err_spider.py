import scrapy
import re
import dateparser
from datetime import datetime, timedelta
from news_scraper.spiders.smart_spider import SmartSpider


class EeErrSpider(SmartSpider):
    name = "ee_err"
    source_timezone = 'Europe/Tallinn'

    country_code = 'EST'
    country = '爱沙尼亚'
    language = 'en'

    # European date format (DD.MM.YY) used in listing lead text
    dateparser_settings = {'DATE_ORDER': 'DMY', 'PREFER_DATES_FROM': 'current_period'}

    allowed_domains = ["news.err.ee"]

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.8,
    }

    use_curl_cffi = True
    playwright = True

    fallback_content_selector = 'article.prime, div.body'

    def start_requests(self):
        yield scrapy.Request(
            "https://news.err.ee/k/business",
            callback=self.parse,
            meta={"playwright": True},
            dont_filter=True,
        )

    def parse(self, response):
        """Parse single-page listing: https://news.err.ee/k/business (no pagination)."""
        articles = response.css('.category-item')
        has_valid_item_in_window = False

        for article in articles:
            link = article.css('p.category-news-header a::attr(href)').get()
            if not link:
                continue
            if not link.startswith('http'):
                link = response.urljoin(link)

            # Extract date from .category-news-lead: "DD.MM.YY NEWS ..."
            publish_time = self._extract_listing_date(article)

            if not self.should_process(link, publish_time):
                continue

            has_valid_item_in_window = True

            yield scrapy.Request(
                link,
                callback=self.parse_detail,
                meta={
                    "playwright": True,
                    "publish_time_hint": publish_time,
                },
                dont_filter=self.full_scan,
            )

        if not has_valid_item_in_window:
            self.logger.info("No new articles in window; stopping.")

    def _extract_listing_date(self, article_sel):
        """Extract date from a listing item. The .category-news-lead text starts
        with 'DD.MM.YY NEWS ...' (e.g. '02.05.26 NEWS ...')."""
        lead_text = article_sel.css('.category-news-lead::text').get()
        if not lead_text:
            return None
        lead_text = lead_text.strip()
        date_match = re.match(r'(\d{2}\.\d{2}\.\d{2,4})', lead_text)
        if not date_match:
            return None
        raw_date = date_match.group(1)
        dt_obj = dateparser.parse(raw_date, settings=self.dateparser_settings)
        return self.parse_to_utc(dt_obj)

    def parse_detail(self, response):
        """Parse article detail page. The primary date source is the time.pubdate
        @datetime attribute (always server-rendered ISO timestamp). The listing-
        page hint serves as fallback."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//time[@class='pubdate']/@datetime",
        )

        item['author'] = "ERR Estonia"
        item['section'] = "Business"

        yield item

    # ------------------------------------------------------------------
    # Retained from the old spider: text-based "Yesterday" parsing for
    # emergencies where the @datetime attribute is somehow unavailable and
    # the Playwright-rendered text reads "Yesterday HH:MM".
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_yesterday_text(date_str):
        """Handle 'Yesterday HH:MM' style date strings as a last resort."""
        yesterday = datetime.now() - timedelta(days=1)
        time_match = re.search(r'(\d{2}:\d{2})', date_str)
        if time_match:
            h, m = map(int, time_match.group(1).split(':'))
            return yesterday.replace(hour=h, minute=m, second=0, microsecond=0)
        return yesterday
