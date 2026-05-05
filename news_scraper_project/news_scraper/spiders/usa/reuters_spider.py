import re
import scrapy
from datetime import datetime
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider
from scrapy_playwright.page import PageMethod


class USAReutersSpider(SmartSpider):
    name = 'usa_reuters'
    source_timezone = 'America/New_York'

    country_code = 'USA'
    country = '美国'
    language = 'en'
    allowed_domains = ['reuters.com']
    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = "div[data-testid='article-body'], .article-body__content"

    section_urls = {
        'business/finance': 'https://www.reuters.com/business/finance/',
        'markets/us': 'https://www.reuters.com/markets/us/',
        'world/us': 'https://www.reuters.com/world/us/',
    }

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
    }

    async def start(self):
        for section, url in self.section_urls.items():
            yield scrapy.Request(
                url,
                callback=self.parse_section_page,
                meta={
                    'section_hint': section,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'domcontentloaded'),
                        PageMethod('wait_for_timeout', 2000),
                    ],
                },
            )

    def parse_section_page(self, response):
        section = response.meta['section_hint']
        seen_on_page = set()
        has_valid_item_in_window = False

        for href in response.css('a::attr(href)').getall():
            if not href:
                continue

            full_url = response.urljoin(href)
            if full_url in seen_on_page:
                continue
            if not full_url.startswith('https://www.reuters.com/'):
                continue
            if '/video/' in full_url or '/graphics/' in full_url or '/podcasts/' in full_url:
                continue
            if any(skip in full_url for skip in ['/world/', '/business/', '/markets/']) is False:
                continue

            seen_on_page.add(full_url)

            # Extract date from URL pattern: /2026/03/15/title/
            publish_time = None
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', full_url)
            if date_match:
                try:
                    publish_time = datetime(
                        int(date_match.group(1)),
                        int(date_match.group(2)),
                        int(date_match.group(3)),
                    )
                except ValueError:
                    pass

            if not self.should_process(full_url, publish_time):
                continue

            has_valid_item_in_window = True
            meta = {
                'section_hint': section,
                'playwright': True,
                'playwright_page_methods': [
                    PageMethod('wait_for_load_state', 'domcontentloaded'),
                    PageMethod('wait_for_timeout', 1500),
                ],
            }
            if publish_time:
                meta['publish_time_hint'] = publish_time
            yield scrapy.Request(full_url, callback=self.parse_detail, meta=meta)

        # Reuters uses infinite scroll. The initial Playwright load provides
        # a substantial set of articles. No explicit page-based pagination.

    def parse_detail(self, response):
        item = self.auto_parse_item(response)

        # ContentEngine fallback: Reuters specific structure
        if not item.get('content_plain'):
            body = (
                response.css('div[data-testid="article-body"]').get()
                or response.css('div.article-body__content').get()
            )
            if body:
                soup = BeautifulSoup(body, 'html.parser')
                content = "\n\n".join(
                    [p.get_text().strip() for p in soup.find_all('p') if len(p.get_text()) > 20]
                )
                if content:
                    item['content_plain'] = content

        item['author'] = 'Reuters'
        item['section'] = response.meta.get('section_hint', 'USA Finance')

        yield item
