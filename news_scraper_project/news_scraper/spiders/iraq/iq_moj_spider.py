import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class IqMojSpider(SmartSpider):
    name = "iq_moj"

    country_code = 'IRQ'
    country = '伊拉克'
    language = 'ar'
    source_timezone = 'Asia/Baghdad'

    allowed_domains = ["moj.gov.iq"]

    use_curl_cffi = True

    # Hint dateparser to prefer Arabic locale for dates like "29/03/2026 - 02:07 صباحًا"
    dateparser_settings = {'languages': ['ar']}

    # Fallback selector for content extraction (known detail-page content containers)
    fallback_content_selector = 'div.article-content-container, div.article-body'

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1
    }

    def start_requests(self):
        yield scrapy.Request(
            url="https://www.moj.gov.iq/news/",
            callback=self.parse,
            dont_filter=True
        )

    def parse(self, response):
        link_els = response.css('a[href^="/view."]')
        self.logger.info(f"Listing Page: Found {len(link_els)} links on {response.url}")

        has_valid_item_in_window = False
        for link_el in link_els:
            href = link_el.css('::attr(href)').get()
            if not href:
                continue
            url = response.urljoin(href)

            # Try to extract a date from the listing page by looking inside the same
            # ancestor container as the link element.  Falls back gracefully when
            # the listing page has no date markup.
            publish_time = None
            date_raw = link_el.xpath(
                './ancestor::*[self::div or self::li or self::article][1]'
                '//*[contains(@class,"date") or contains(@class,"meta") or contains(@class,"time")]//text()'
            ).get()
            if date_raw:
                publish_time = self.parse_date(date_raw.strip())

            if not self.should_process(url, publish_time):
                if publish_time and self.cutoff_date and publish_time < self.cutoff_date:
                    self.logger.info(
                        f"Hit date boundary at {publish_time}. Stopping pagination."
                    )
                    has_valid_item_in_window = False
                    break
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url=url,
                callback=self.parse_article,
                dont_filter=self.full_scan,
                meta={'publish_time_hint': publish_time}
            )

        # Paginate only when we saw at least one in-window item
        if has_valid_item_in_window:
            next_page = response.css('a.next-page::attr(href)').get()
            if next_page:
                yield scrapy.Request(
                    url=response.urljoin(next_page),
                    callback=self.parse,
                    dont_filter=True
                )

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class, 'article-title')]/text()",
            publish_time_xpath="//span[contains(@class, 'meta-date')]/text()"
        )

        # Refine publish_time: prefer the hint from the listing page, then fall
        # back to manual extraction of the Arabic AM/PM date format.
        publish_time_hint = response.meta.get('publish_time_hint')
        if publish_time_hint and not item.get('publish_time'):
            item['publish_time'] = publish_time_hint

        if not item.get('publish_time'):
            date_raw = response.css('span.meta-date::text').get('').strip()
            if date_raw:
                try:
                    # Normalise Arabic AM/PM before parsing
                    date_norm = date_raw.replace('صباحًا', 'AM').replace('مساءً', 'PM')
                    pub_date = datetime.strptime(date_norm, '%d/%m/%Y - %I:%M %p')
                    item['publish_time'] = self.parse_to_utc(pub_date)
                except Exception as e:
                    self.logger.debug(f"Manual date parse error: {e} for '{date_raw}'")

        # Final gate: reject items that are still outside the incremental window
        if not self.should_process(response.url, item.get('publish_time')):
            return

        # Metadata defaults
        if not item.get('author'):
            item['author'] = 'Ministry of Justice - Iraq'
        item['section'] = 'News'

        if item.get('content_plain') or item.get('content_markdown'):
            yield item
