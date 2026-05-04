import scrapy
import json
import re
import dateparser
from scrapy_playwright.page import PageMethod
from news_scraper.spiders.smart_spider import SmartSpider


class GeBpnSpider(SmartSpider):
    name = "ge_bpn"

    country_code = 'GEO'
    country = '格鲁吉亚'
    source_timezone = 'Asia/Tbilisi'
    language = 'ka'
    start_date = '2024-01-01'
    use_curl_cffi = True

    allowed_domains = ["www.bpn.ge"]
    start_urls = ["https://www.bpn.ge/category/161-ekonomika/"]

    # Georgian / European date format (DD.MM.YYYY)
    dateparser_settings = {'DATE_ORDER': 'DMY', 'PREFER_DATES_FROM': 'current_period'}

    # The list page is JavaScript-rendered with only LD+JSON for static data.
    # Individual article dates are not available in the listing; dates are
    # extracted from detail pages. We use the page-level dateModified as
    # a rough filter and collect precise dates on detail pages.
    strict_date_required = False

    fallback_content_selector = '.article_body_wrapper'

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled"]
        }
    }

    def parse(self, response):
        """Parse list page: extract links from LD+JSON, use page-level date for filtering."""
        result = self._parse_listing_ldjson(response)
        article_urls = result['urls']
        page_date = result['page_date_modified']
        headlines = result['headlines']  # URL -> headline map

        self.logger.info(f"GE_BPN List: Found {len(article_urls)} articles on {response.url}")

        has_valid_item_in_window = False

        for url in article_urls:
            # Use page-level dateModified as approximate publish_time for filtering.
            # Prefer None over approximate date to avoid blocking real articles.
            if not self.should_process(url, publish_time=None):
                continue

            has_valid_item_in_window = True

            yield scrapy.Request(
                url,
                callback=self.parse_article,
                meta={
                    "playwright": True,
                    "title_hint": headlines.get(url),
                    "publish_time_hint": page_date,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "domcontentloaded", timeout=30000),
                    ]
                },
                dont_filter=self.full_scan,
            )

        # Pagination: stop when page has no new (non-duplicate) items
        if has_valid_item_in_window:
            match = re.search(r'page=(\d+)', response.url)
            current_page = int(match.group(1)) if match else 1
            next_page_url = f"https://www.bpn.ge/category/161-ekonomika/?page={current_page + 1}"
            yield scrapy.Request(next_page_url, callback=self.parse, dont_filter=True)

    def _parse_listing_ldjson(self, response):
        """
        Parse all LD+JSON scripts on the list page.

        Returns dict with:
          - urls: list of article URLs
          - page_date_modified: datetime or None (page-level modification time)
          - headlines: dict of url -> headline from hasPart
        """
        article_urls = []
        page_date_modified = None
        headlines = {}

        scripts = response.css('script[type="application/ld+json"]::text').getall()
        for s in scripts:
            try:
                data = json.loads(s)
                if not isinstance(data, dict):
                    continue

                # 1. Extract article URLs from mainEntity.itemListElement
                main_entity = data.get('mainEntity')
                if isinstance(main_entity, dict):
                    items = main_entity.get('itemListElement', [])
                    for entry in items:
                        url = None
                        if isinstance(entry, dict):
                            url = entry.get('item') if isinstance(entry.get('item'), str) else entry.get('url')
                        if isinstance(url, str) and '/article/' in url:
                            article_urls.append(url)

                # 2. Extract page-level dateModified
                raw_date = data.get('dateModified')
                if raw_date:
                    dt = self.parse_date(raw_date)
                    if dt:
                        page_date_modified = dt

                # 3. Extract headlines from hasPart (NewsArticle list)
                has_part = data.get('hasPart', [])
                if isinstance(has_part, list):
                    for article in has_part:
                        if isinstance(article, dict) and article.get('@type') == 'NewsArticle':
                            article_url = article.get('url')
                            headline = article.get('headline')
                            if article_url and headline:
                                headlines[article_url] = headline

                # 4. Also check flat itemListElement (BreadcrumbList style)
                flat_items = data.get('itemListElement', [])
                if isinstance(flat_items, list) and not article_urls:
                    for entry in flat_items:
                        url = entry.get('item') if isinstance(entry, dict) else entry
                        if isinstance(url, str) and '/article/' in url:
                            article_urls.append(url)

            except Exception:
                pass

        # Fallback: regex extraction if no URLs found
        if not article_urls:
            article_urls = list(set(re.findall(
                r'https://www\.bpn\.ge/article/[\w-]+/', response.text
            )))

        # Deduplicate while preserving order
        seen = set()
        unique_urls = []
        for url in article_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return {
            'urls': unique_urls,
            'page_date_modified': page_date_modified,
            'headlines': headlines,
        }

    def parse_article(self, response):
        """Parse detail page using SmartSpider auto_parse_item."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
        )

        item['author'] = "BPN.ge"
        item['section'] = "Economy"

        yield item
