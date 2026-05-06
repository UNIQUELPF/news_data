import scrapy
import re
import dateparser
from scrapy_playwright.page import PageMethod
from news_scraper.spiders.smart_spider import SmartSpider


class CzPatriaSpider(SmartSpider):
    name = "cz_patria"
    source_timezone = 'Europe/Prague'

    country_code = 'CZE'
    country = '捷克'
    language = 'cs'

    allowed_domains = ["www.patria.cz"]

    fallback_content_selector = (
        '#ctl00_ctl00_ctl00_MC_Content_centerColumnPlaceHolder_Detail, '
        '.article-body'
    )

    # European date format: DD.MM.YYYY HH:MM
    dateparser_settings = {'DATE_ORDER': 'DMY'}

    # When no date on listing page, fall back to detail page extraction.
    # The listing page has .datetime elements, so we keep strict mode.
    strict_date_required = True

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True}
    }

    use_curl_cffi = True
    playwright = True

    async def start(self):
        yield scrapy.Request(
            "https://www.patria.cz/zpravodajstvi/zpravy.html",
            callback=self.parse,
            dont_filter=True,
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod(
                        "wait_for_selector",
                        "a[href^='/zpravodajstvi/'][title]",
                        timeout=15000,
                    ),
                ],
            },
        )

    def parse(self, response):
        """
        Parse listing page: https://www.patria.cz/zpravodajstvi/zpravy.html

        Each article block:
          <div><div class="datetime">DD.MM.YYYY HH:MM</div><div class="title"><a href="...">...</a></div></div>

        Pagination is AJAX-based (Playwright click on .pagenavigator a.goto).
        """
        has_valid_item_in_window = False

        for dt_div in response.css('div.datetime'):
            date_text = dt_div.css('::text').get()
            if not date_text:
                continue

            # Navigate to parent and find the sibling .title anchor
            parent = dt_div.xpath('..')
            a_elem = parent.css('.title a')
            link = a_elem.css('::attr(href)').get()
            if not link or '/zpravodajstvi/' not in link:
                continue

            if not link.startswith('http'):
                link = response.urljoin(link)

            title_text = a_elem.css('::attr(title)').get()

            # Parse date from listing page
            publish_time = None
            try:
                dt_obj = dateparser.parse(
                    date_text.strip(), settings={'DATE_ORDER': 'DMY'}
                )
                publish_time = self.parse_to_utc(dt_obj)
            except Exception as e:
                self.logger.warning(f"Date parse error for {link}: {e}")

            if not self.should_process(link, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                link,
                callback=self.parse_article,
                meta={
                    "title_hint": title_text,
                    "publish_time_hint": publish_time,
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "h1", timeout=10000),
                    ],
                },
            )

        # Playwright click-based AJAX pagination with circuit breaker
        if not has_valid_item_in_window:
            self.logger.info(
                "No valid items in window — stopping pagination."
            )
            return

        current_page_text = response.css(
            '.pagenavigator span.active::text'
        ).get()
        if not current_page_text:
            return

        try:
            next_page_num = int(current_page_text) + 1
        except ValueError:
            return

        next_selector = f'.pagenavigator a.goto[title="{next_page_num}"]'
        yield scrapy.Request(
            response.url,
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod("click", next_selector),
                    PageMethod("wait_for_timeout", 3000),
                    PageMethod(
                        "wait_for_selector",
                        "a[href^='/zpravodajstvi/'][title]",
                    ),
                ],
            },
            dont_filter=True,
        )

    def parse_article(self, response):
        """
        Parse article detail page using SmartSpider auto_parse_item.

        Date is extracted from div.author > div.datetime.
        Content engine uses fallback_content_selector for body extraction.
        """
        item = self.auto_parse_item(
            response,
            publish_time_xpath=(
                "//div[contains(@class,'author')]"
                "/div[contains(@class,'datetime')]/text()"
            ),
        )

        # Fallback: full-page regex for DD.MM.YYYY HH:MM if XPath misses
        if not item.get('publish_time'):
            date_match = re.search(
                r'(\d{2}\.\d{2}\.\d{4}\s+\d{1,2}:\d{2})',
                response.text,
            )
            if date_match:
                try:
                    dt_obj = dateparser.parse(
                        date_match.group(1), settings={'DATE_ORDER': 'DMY'}
                    )
                    item['publish_time'] = self.parse_to_utc(dt_obj)
                except Exception as e:
                    self.logger.warning(
                        f"Regex date fallback failed for {response.url}: {e}"
                    )

        item['author'] = "Patria.cz"
        item['section'] = "News"

        yield item
