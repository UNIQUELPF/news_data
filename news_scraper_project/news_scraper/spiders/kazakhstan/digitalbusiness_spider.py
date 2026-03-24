import scrapy
from scrapy_playwright.page import PageMethod
from news_scraper.items import DigitalBusinessItem
from datetime import datetime
import re
from news_scraper.utils import get_dynamic_cutoff

class DigitalBusinessSpider(scrapy.Spider):
    name = 'digitalbusiness'
    allowed_domains = ['digitalbusiness.kz']
    
    # Global cutoff date will be set dynamically in from_crawler
    CUTOFF_DATE = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(DigitalBusinessSpider, cls).from_crawler(crawler, *args, **kwargs)
        # Use dynamic cutoff logic
        spider.CUTOFF_DATE = get_dynamic_cutoff(crawler.settings, 'news_digitalbusiness')
        return spider

    # Base URL
    BASE_URL = 'https://digitalbusiness.kz'

    # Sections to scrape
    SECTIONS = {
        'IT-Startups': '/it-i-startapy/',
        'Finance': '/finance/',
        'Latest': '/last/'
    }

    custom_settings = {
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1.0,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'PLAYWRIGHT_MAX_CONTEXTS': 4,
        'PLAYWRIGHT_MAX_PAGES_PER_CONTEXT': 2,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    def start_requests(self):
        for category, path in self.SECTIONS.items():
            url = self.BASE_URL + path
            yield scrapy.Request(
                url,
                callback=self.parse_list,
                meta={
                    'category': category,
                    'page': 1,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_selector', 'a.pcb_wrap', timeout=30000)
                    ]
                }
            )

    def parse_list(self, response):
        category = response.meta['category']
        current_page = response.meta['page']
        
        # Log response body length to see if we got content
        self.logger.info(f"[{category}] Page {current_page} response length: {len(response.body)}")
        
        # Try both CSS and XPath
        articles = response.css('a.pcb_wrap')
        if not articles:
            articles = response.xpath('//a[contains(@class, "pcb_wrap")]')
            
        self.logger.info(f"[{category}] Found {len(articles)} article links on page {current_page}")

        found_valid_date = False

        for art in articles:
            link = art.css('::attr(href)').get()
            title = art.css('.pcb_title::text').get()
            date_str = art.css('.pcb_date::text').get()
            
            if link:
                url = response.urljoin(link)
                # Primary date check in list
                publish_time = self._parse_russian_date(date_str)
                
                if publish_time:
                    if publish_time < self.CUTOFF_DATE:
                        self.logger.info(f"[{category}] Article {url} dated {publish_time} is before cutoff. Stopping section.")
                        return # Stop this section

                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    meta={
                        'category': category,
                        'title': title,
                        'playwright': True,
                        'playwright_page_methods': [
                            PageMethod('wait_for_timeout', 1500),
                            PageMethod('wait_for_selector', 'h1', timeout=15000)
                        ]
                    }
                )
                found_valid_date = True

        # Pagination: /page/N/
        if found_valid_date:
            next_page = current_page + 1
            section_path = self.SECTIONS[category]
            next_url = f"{self.BASE_URL}{section_path}/page/{next_page}/"
            
            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={
                    'category': category,
                    'page': next_page,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_timeout', 2000),
                        PageMethod('wait_for_selector', 'a.pcb_wrap', timeout=20000)
                    ]
                }
            )

    def parse_detail(self, response):
        category = response.meta['category']
        
        title = response.css('h1::text').get()
        if not title:
            title = response.meta.get('title')
        
        # Date often found in a string like "Дата публикации: 02.03.2026, 10:24"
        # Or sometimes just a time element
        date_text = response.xpath('//p[contains(text(), "Дата публикации")]/text()').get()
        if not date_text:
            date_text = response.css('time::text').get()
            
        publish_time = self._parse_russian_date(date_text)
        
        # If published date is before cutoff, ignore
        if publish_time and publish_time < self.CUTOFF_DATE:
            return

        # Content is in .content_col
        content_parts = response.css('.content_col p::text, .content_col h2::text, .content_col h3::text, .content_col blockquote::text').getall()
        if not content_parts:
            # Fallback
            content_parts = response.css('.content_col ::text').getall()
            
        content = "\n\n".join([p.strip() for p in content_parts if p.strip()])
        
        # Clean content from noise
        if not title or len(content) < 100:
            return

        item = DigitalBusinessItem()
        item['type'] = 'digitalbusiness'
        item['category'] = category
        item['title'] = title.strip() if title else ""
        item['url'] = response.url
        item['publish_time'] = publish_time
        item['content'] = content
        item['crawl_time'] = datetime.now()
        
        yield item

    def _parse_russian_date(self, date_str):
        if not date_str:
            return None
        
        date_str = date_str.lower().strip()
        
        # Handle "Дата публикации: ..." prefix
        if 'дата публикации:' in date_str:
            date_str = date_str.replace('дата публикации:', '').strip()

        # Month mapping
        months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
            'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
            'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
        }

        # Case 1: 02.03.2026, 10:24
        match_full = re.search(r'(\d{2})\.(\d{2})\.(\d{4})(?:,\s*(\d{1,2}):(\d{2}))?', date_str)
        if match_full:
            d, m, y, hh, mm = match_full.groups()
            return datetime(int(y), int(m), int(d), int(hh) if hh else 0, int(mm) if mm else 0)

        # Case 2: 02 марта 2026
        for m_name, m_num in months.items():
            if m_name in date_str:
                match = re.search(fr'(\d{{1,2}})\s+{m_name}\s+(\d{{4}})', date_str)
                if match:
                    day, year = match.groups()
                    return datetime(int(year), m_num, int(day))

        # Case 3: Сегодня, Вчера (if any)
        now = datetime.now()
        if 'сегодня' in date_str:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if 'вчера' in date_str:
            from datetime import timedelta
            yesterday = now - timedelta(days=1)
            return yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

        return None
