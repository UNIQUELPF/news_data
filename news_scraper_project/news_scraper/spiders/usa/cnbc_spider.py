import json
import re
import scrapy
from datetime import datetime
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider


class USACNBCSpider(SmartSpider):
    name = 'usa_cnbc'
    source_timezone = 'America/New_York'

    country_code = 'USA'
    country = '美国'
    language = 'en'
    start_date = '2026-01-01'
    allowed_domains = ['cnbc.com']
    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = ".ArticleBody-articleBody, div.group"

    section_urls = [
        'https://www.cnbc.com/economy/',
        'https://www.cnbc.com/finance/',
        'https://www.cnbc.com/cnbc-investigations/',
        'https://www.cnbc.com/ai-artificial-intelligence/',
        'https://www.cnbc.com/energy/'
    ]

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }

    async def start(self):
        for url in self.section_urls:
            section_name = url.strip('/').split('/')[-1]
            yield scrapy.Request(url, callback=self.parse, meta={'section_hint': url})

    def parse(self, response):
        if self._stop_pagination:
            return
        section_hint = response.meta.get('section_hint', '')

        # Try Next.js structured data
        next_data_str = response.xpath('//script[@id="__NEXT_DATA__"]/text()').get()
        if next_data_str:
            try:
                json.loads(next_data_str)
            except Exception:
                pass

        # CSS extraction
        articles = response.css('a.Card-title::attr(href)').getall()
        has_valid_item_in_window = False

        for link in articles:
            if not link or not link.startswith('https') or '/202' not in link:
                continue

            # Extract date from URL pattern: /2026/03/15/title/
            publish_time = None
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', link)
            if date_match:
                try:
                    publish_time = datetime(
                        int(date_match.group(1)),
                        int(date_match.group(2)),
                        int(date_match.group(3)),
                    )
                except ValueError:
                    pass

            if not self.should_process(link, publish_time):
                continue

            has_valid_item_in_window = True
            meta = {'section_hint': section_hint}
            if publish_time:
                meta['publish_time_hint'] = publish_time
            yield scrapy.Request(link, callback=self.parse_detail, meta=meta)

        # CNBC GraphQL pagination placeholder
        if has_valid_item_in_window:
            section_name = section_hint.strip('/').split('/')[-1]
            yield from self.request_api_page(section_name, offset=30)

    def request_api_page(self, section_name, offset):
        """CNBC GraphQL pagination placeholder - implement with actual API endpoint when available."""
        pass

    def parse_detail(self, response):
        item = self.auto_parse_item(response)

        # ContentEngine fallback: CNBC specific cleaning
        if not item.get('content_plain'):
            content_parts = []
            body = response.css('.ArticleBody-articleBody')
            if not body:
                body = response.css('div.group')

            if body:
                soup = BeautifulSoup(body.get(), 'html.parser')
                for tag in soup(['script', 'style', 'aside', 'button', 'nav']):
                    tag.decompose()
                for p in soup.find_all(['p', 'div']):
                    text = p.get_text().strip()
                    if len(text) > 40:
                        content_parts.append(text)
            if content_parts:
                item['content_plain'] = '\n\n'.join(content_parts)

        item['author'] = response.css('a.Author-authorName::text').get() or 'CNBC'
        item['section'] = response.meta.get('section_hint', 'USA Business')

        yield item
