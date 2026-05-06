import scrapy
from datetime import datetime
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider


class USAYFinanceSpider(SmartSpider):
    name = 'usa_yfinance'
    source_timezone = 'America/New_York'

    country_code = 'USA'
    country = '美国'
    language = 'en'
    start_date = '2026-01-01'
    allowed_domains = ['finance.yahoo.com']
    strict_date_required = False  # List page dates unreliable; extracted on detail pages
    use_curl_cffi = True
    fallback_content_selector = "article.article-wrap, div.body-wrap, article"

    start_urls = ['https://finance.yahoo.com/topic/latest-news/']

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
    }

    async def start(self):
        yield scrapy.Request(self.start_urls[0], callback=self.parse, meta={'page': 1}, dont_filter=True)

    def parse(self, response):
        articles = response.css('a.subtle-link.fin-size-small::attr(href)').getall()
        if not articles:
            articles = response.xpath('//ul//li//a[contains(@href, "/news/")]/@href').getall()

        has_valid_item_in_window = False
        for link in articles:
            full_url = response.urljoin(link)
            if '/news/' not in full_url:
                continue

            # strict_date_required=False allows passing None for publish_time
            if not self.should_process(full_url, None):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(full_url, callback=self.parse_detail)

        # Circuit breaker: stop pagination when no new articles found
        if has_valid_item_in_window:
            current_page = response.meta.get('page', 1)
            next_page = current_page + 1
            next_url = f"{self.start_urls[0]}{next_page}/"
            yield scrapy.Request(next_url, callback=self.parse, meta={'page': next_page})

    def parse_detail(self, response):
        item = self.auto_parse_item(response)

        # Safety check: filter articles before cutoff date
        pub_time = item.get('publish_time')
        if pub_time and self.cutoff_date and pub_time < self.cutoff_date:
            return

        # ContentEngine fallback: Yahoo Finance specific cleaning
        if not item.get('content_plain'):
            content_html = response.css('article.article-wrap').get() or response.css('div.body-wrap').get() or response.css('article').get()
            if content_html:
                soup = BeautifulSoup(content_html, 'html.parser')
                for tag in soup(['script', 'style', 'button', 'svg', 'canvas']):
                    tag.decompose()
                text = soup.get_text(separator='\n')
                lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) > 30]
                if lines:
                    item['content_plain'] = '\n\n'.join(lines)

        item['author'] = response.css('span.caas-author-byline-collapse::text').get() or 'Yahoo Finance'
        item['section'] = 'Latest News'

        if item.get('content_plain') and len(item['content_plain']) > 100:
            yield item
