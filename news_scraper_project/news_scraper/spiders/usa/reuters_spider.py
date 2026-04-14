from datetime import datetime

import scrapy
from news_scraper.spiders.base_spider import BaseNewsSpider
from scrapy_playwright.page import PageMethod


class USAReutersSpider(BaseNewsSpider):
    name = 'usa_reuters'

    country_code = 'USA'

    country = '美国'
    allowed_domains = ['reuters.com']
    section_urls = {
        'business/finance': 'https://www.reuters.com/business/finance/',
        'markets/us': 'https://www.reuters.com/markets/us/',
        'world/us': 'https://www.reuters.com/world/us/',
    }
    
    # 继承 BaseNewsSpider，自动初始化 usa_reuters_news 表
    target_table = 'usa_reuters_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    def iter_start_requests(self):
        for section, url in self.section_urls.items():
            yield scrapy.Request(
                url,
                callback=self.parse_section_page,
                meta={
                    'section': section,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'domcontentloaded'),
                        PageMethod('wait_for_timeout', 2000),
                    ],
                },
            )

    def start_requests(self):
        yield from self.iter_start_requests()

    async def start(self):
        for request in self.iter_start_requests():
            yield request

    def parse_section_page(self, response):
        section = response.meta['section']
        seen_links = set()

        for href in response.css('a::attr(href)').getall():
            if not href:
                continue

            full_url = response.urljoin(href)
            if full_url in seen_links or full_url in self.scraped_urls:
                continue
            if not full_url.startswith('https://www.reuters.com/'):
                continue
            if '/video/' in full_url or '/graphics/' in full_url or '/podcasts/' in full_url:
                continue
            if any(skip in full_url for skip in ['/world/', '/business/', '/markets/']) is False:
                continue

            seen_links.add(full_url)
            self.scraped_urls.add(full_url)
            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
                meta={
                    'section': section,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'domcontentloaded'),
                        PageMethod('wait_for_timeout', 1500),
                    ],
                },
            )

    def parse_article(self, response):
        from bs4 import BeautifulSoup

        title = (
            response.css('h1[data-testid="Heading"]::text').get()
            or response.css('h1::text').get()
            or response.xpath('//meta[@property="og:title"]/@content').get()
        )

        body = (
            response.css('div[data-testid="article-body"]').get()
            or response.css('div.article-body__content').get()
        )
        content = ""
        if body:
            soup = BeautifulSoup(body, 'html.parser')
            content = "\n\n".join([p.get_text().strip() for p in soup.find_all('p') if len(p.get_text()) > 20])

        pub_time = response.meta.get('pub_time')
        if not pub_time:
            pub_time_str = (
                response.xpath('//meta[@property="article:published_time"]/@content').get()
                or response.css('time::attr(datetime)').get()
            )
            if pub_time_str:
                try:
                    pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00')).replace(tzinfo=None)
                except Exception:
                    pub_time = None

        if not self.filter_date(pub_time):
            return

        yield {
            'url': response.url,
            'title': title.strip() if title else 'Unknown',
            'content': content,
            'publish_time': pub_time,
            'author': 'Reuters',
            'language': 'en',
            'section': response.meta.get('section', 'USA Finance'),
        }
