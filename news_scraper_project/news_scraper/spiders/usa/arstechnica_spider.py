import re
import scrapy
from datetime import datetime
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider


class USAArsTechnicaSpider(SmartSpider):
    name = 'usa_arstechnica'
    source_timezone = 'America/New_York'

    country_code = 'USA'
    country = '美国'
    language = 'en'
    start_date = '2026-01-01'
    allowed_domains = ['arstechnica.com']
    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = ".article-content, div[itemprop='articleBody']"

    start_urls = ['https://arstechnica.com/']

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
    }

    async def start(self):
        yield scrapy.Request(self.start_urls[0], callback=self.parse, meta={'page': 1}, dont_filter=True)

    def parse(self, response):
        articles = response.css('li.article h2 a::attr(href)').getall()
        featured = response.css('header.article h2 a::attr(href)').getall()

        has_valid_item_in_window = False
        for link in set(articles + featured):
            if not link or not link.startswith('https') or '/20' not in link:
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
            meta = {}
            if publish_time:
                meta['publish_time_hint'] = publish_time
            yield scrapy.Request(link, callback=self.parse_detail, meta=meta)

        # Circuit breaker: when articles are too old, stop pagination
        if has_valid_item_in_window:
            current_page = response.meta.get('page', 1)
            next_page = current_page + 1
            next_url = f"{self.start_urls[0]}page/{next_page}/"
            yield scrapy.Request(next_url, callback=self.parse, meta={'page': next_page})

    def parse_detail(self, response):
        item = self.auto_parse_item(response)

        # ContentEngine fallback: Ars Technica specific cleaning
        if not item.get('content_plain'):
            content_html = response.css('.article-content').get() or response.css('div[itemprop="articleBody"]').get()
            if content_html:
                soup = BeautifulSoup(content_html, 'html.parser')
                for tag in soup(['script', 'style', 'aside', 'footer', 'div.ad-wrapper', 'div.gallery-popover-image']):
                    tag.decompose()
                paragraphs = soup.find_all(['p', 'h2', 'h3'])
                content_parts = []
                for p in paragraphs:
                    text = p.get_text().strip()
                    if len(text) > 30 and 'Ars Technica' not in text:
                        content_parts.append(text)
                if content_parts:
                    item['content_plain'] = '\n\n'.join(content_parts)

        item['author'] = response.css('span[itemprop="name"]::text').get() or 'Ars Technica'
        item['section'] = response.css('nav.article-section a::text').get() or 'Technology'

        if item.get('content_plain') and len(item['content_plain']) > 150:
            yield item
