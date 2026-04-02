# 哈萨克斯坦inbusiness spider爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from scrapy_playwright.page import PageMethod
from news_scraper.items import InBusinessItem
from datetime import datetime
import re
from news_scraper.utils import get_dynamic_cutoff

class InBusinessSpider(scrapy.Spider):
    name = 'inbusiness'
    allowed_domains = ['inbusiness.kz']
    
    # Global cutoff date will be set dynamically in from_crawler
    CUTOFF_DATE = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(InBusinessSpider, cls).from_crawler(crawler, *args, **kwargs)
        # Use dynamic cutoff logic
        spider.CUTOFF_DATE = get_dynamic_cutoff(crawler.settings, 'news_inbusiness')
        return spider

    # Base URL for categories
    BASE_URL = 'https://inbusiness.kz'

    # Sections to scrape from the menu
    SECTIONS = {
        'Business': '/ru/cat/biznes',
        'Finance': '/ru/cat/finansy',
        'Economy': '/ru/cat/ekonomika',
        'Country': '/ru/cat/strana',
        'Property': '/ru/cat/nedvizhimost',
        'World': '/ru/cat/mir',
        'Tech': '/ru/cat/tehnologii',
        'Auto': '/ru/cat/avto',
        'Sport': '/ru/cat/sport',
        'Lifestyle': '/ru/cat/stil-zhizni',
        'Experts': '/ru/authors',
        'Appointments': '/ru/appointments'
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
                        PageMethod('wait_for_timeout', 2000),
                        PageMethod('wait_for_selector', 'a[href^="/ru/news/"]', timeout=20000)
                    ]
                }
            )

    def parse_list(self, response):
        category = response.meta['category']
        current_page = response.meta['page']
        
        # InBusiness uses links with <span> for titles and <time> for dates
        articles = response.css('a[href^="/ru/news/"]')
        self.logger.info(f"[{category}] Found {len(articles)} article links on page {current_page}")

        found_valid_date = False
        last_article_date = None

        for art in articles:
            link = art.css('::attr(href)').get()
            title = art.css('span::text').get()
            date_str = art.css('time::text').get()
            
            if link:
                url = response.urljoin(link)
                publish_time = self._parse_russian_date(date_str)
                
                if publish_time:
                    last_article_date = publish_time
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

        # Pagination: ?page=N
        # If we found articles and didn't trigger the cutoff, try next page
        if found_valid_date:
            next_page = current_page + 1
            section_path = self.SECTIONS[category]
            next_url = f"{self.BASE_URL}{section_path}?page={next_page}"
            
            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={
                    'category': category,
                    'page': next_page,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_timeout', 2000),
                        PageMethod('wait_for_selector', 'a[href^="/ru/news/"]', timeout=20000)
                    ]
                }
            )

    def parse_detail(self, response):
        category = response.meta['category']
        
        title = response.css('h1::text').get()
        if not title:
            title = response.meta.get('title')
        
        publish_time = None
        iso_date = response.css('time::attr(datetime)').get()
        if iso_date:
            try:
                # E.g., 2026-03-02T09:00:00+05:00
                dt_str = iso_date[:19]
                publish_time = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
            except Exception:
                pass
                
        if not publish_time:
            date_str = response.css('time::text').get()
            publish_time = self._parse_russian_date(date_str)
            
        # If published date is before cutoff, ignore
        if publish_time and publish_time < self.CUTOFF_DATE:
            return
        
        # Article body is in .text block
        content_parts = response.css('.text p::text, .text h2::text, .text blockquote::text').getall()
        if not content_parts:
            content_parts = response.css('.text ::text').getall()
            
        content = "\n\n".join([p.strip() for p in content_parts if p.strip()])
        
        # Basic validation
        if not title or len(content) < 100:
            return

        item = InBusinessItem()
        item['type'] = 'inbusiness'
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
        
        # Example formats: 
        # "02.03.26, 09:00" (Full detail)
        # "Вчера, 18:30" (Yesterday)
        # "Сегодня, 10:00" (Today)
        # "20.02.26" (Old date)
        
        date_str = date_str.strip()
        now = datetime.now()
        
        try:
            if 'Сегодня' in date_str:
                time_part = re.search(r'(\d{2}:\d{2})', date_str)
                if time_part:
                    h, m = map(int, time_part.group(1).split(':'))
                    return now.replace(hour=h, minute=m, second=0, microsecond=0)
                return now
            
            if 'Вчера' in date_str:
                from datetime import timedelta
                yesterday = now - timedelta(days=1)
                time_part = re.search(r'(\d{2}:\d{2})', date_str)
                if time_part:
                    h, m = map(int, time_part.group(1).split(':'))
                    return yesterday.replace(hour=h, minute=m, second=0, microsecond=0)
                return yesterday

            # Format: DD.MM.YY, HH:MM or DD.MM.YY
            match = re.search(r'(\d{2})\.(\d{2})\.(\d{2})(?:,\s*(\d{1,2}):(\d{2}))?', date_str)
            if match:
                day, month, year, hour, minute = match.groups()
                # Assuming 26 means 2026
                full_year = 2000 + int(year)
                h = int(hour) if hour else 0
                m = int(minute) if minute else 0
                return datetime(full_year, int(month), int(day), h, m)
                
            return None
        except:
            return None
