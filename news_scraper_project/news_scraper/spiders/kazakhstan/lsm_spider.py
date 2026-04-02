# 哈萨克斯坦lsm spider爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from scrapy_playwright.page import PageMethod
from news_scraper.items import LSMItem
from datetime import datetime
import re
from news_scraper.utils import get_dynamic_cutoff

class LSMSpider(scrapy.Spider):
    name = 'lsm'
    allowed_domains = ['lsm.kz']
    
    # Global cutoff date will be set dynamically in from_crawler
    CUTOFF_DATE = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(LSMSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider.CUTOFF_DATE = get_dynamic_cutoff(crawler.settings, 'news_lsm')
        return spider

    # Sections to scrape
    SECTIONS = {
        'Analytics': 'https://lsm.kz/analytics',
        'Banks': 'https://lsm.kz/banks',
        'Exchange': 'https://lsm.kz/exchange',
        'Property': 'https://lsm.kz/property',
        'Appointments': 'https://lsm.kz/appointments',
        'Taxes': 'https://lsm.kz/taxes',
        'Projects': 'https://lsm.kz/projects',
        'Freedom': 'https://lsm.kz/freedom',
        'Markets': 'https://lsm.kz/markets',
        'Company': 'https://lsm.kz/company',
        'Auto': 'https://lsm.kz/auto',
        'Infographics': 'https://lsm.kz/infographics',
        'Archive': 'https://lsm.kz/archive'
    }

    custom_settings = {
        'CONCURRENT_REQUESTS': 4,
        'DOWNLOAD_DELAY': 1.5,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'PLAYWRIGHT_MAX_CONTEXTS': 2,
        'PLAYWRIGHT_MAX_PAGES_PER_CONTEXT': 2,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    def start_requests(self):
        for category, url in self.SECTIONS.items():
            yield scrapy.Request(
                url,
                callback=self.parse_list,
                meta={
                    'category': category,
                    'page': 1,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_timeout', 2000),
                        PageMethod('wait_for_selector', '#mainInnerRightGrid', timeout=20000)
                    ]
                }
            )

    def parse_list(self, response):
        category = response.meta['category']
        current_page = response.meta['page']
        
        # Scrape articles on current page
        articles = response.css('#mainInnerRightGrid a[href^="/"]')
        self.logger.info(f"[{category}] Found {len(articles)} articles on page {current_page}")

        last_article_date = None
        for art in articles:
            # Extract basic info from list
            link = art.css('::attr(href)').get()
            title = art.css('.innerGridElemTxt::text').get()
            date_str = art.css('.innerGridElemDate::text').get()
            
            if link:
                url = response.urljoin(link)
                publish_time = self._parse_russian_date(date_str)
                
                if publish_time:
                    last_article_date = publish_time
                    if publish_time < self.CUTOFF_DATE:
                        self.logger.info(f"[{category}] Article {url} dated {publish_time} is before cutoff. Stopping section.")
                        return # Stop processing this section if we hit old articles
                
                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    meta={
                        'category': category,
                        'title': title, # Pass title if detail page is different
                        'playwright': True,
                        'playwright_page_methods': [
                            PageMethod('wait_for_timeout', 1500),
                            PageMethod('wait_for_selector', 'h1', timeout=15000)
                        ]
                    }
                )

        # Pagination: if we haven't hit old articles, go to next page
        if last_article_date and last_article_date >= self.CUTOFF_DATE:
            next_page = current_page + 1
            # URL pattern: https://lsm.kz/banks/!2
            section_url = self.SECTIONS[category]
            next_url = f"{section_url}/!{next_page}"
            
            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={
                    'category': category,
                    'page': next_page,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_timeout', 2000),
                        PageMethod('wait_for_selector', '#mainInnerRightGrid', timeout=20000)
                    ]
                }
            )

    def parse_detail(self, response):
        category = response.meta['category']
        
        # Refined selectors based on live DOM inspection
        title = response.css('h1#mainArticleLeftTextTopRightHead::text').get()
        if not title:
            title = response.meta.get('title')
        
        date_str = response.css('div#mainArticleLeftTextTopRightStatDate::text').get()
        publish_time = self._parse_russian_date(date_str)
        
        # Refined content selector to exclude sidebar/related news
        content_parts = response.css('article#mainArticleLeftTextFulltext p::text').getall()
        if not content_parts:
            # Fallback if text is not in <p> tags
            content_parts = response.css('article#mainArticleLeftTextFulltext ::text').getall()
            
        content = "\n\n".join([p.strip() for p in content_parts if p.strip()])
        
        if not title or len(content) < 100:
            self.logger.warning(f"Rejected {response.url}: Missing title or short content")
            return

        item = LSMItem()
        item['type'] = 'lsm'
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
        
        # Example: "27 февраля 2026 года" or "26 февраля 2026"
        date_str = date_str.lower().strip()
        
        months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
            'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
            'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
        }
        
        try:
            # Match "D month YYYY" (e.g., "10 февраля 2026 года")
            match = re.search(r'(\d{1,2})\s+([а-я]+)\s+(\d{4})', date_str)
            if match:
                day, month_name, year = match.groups()
                if month_name in months:
                    return datetime(int(year), months[month_name], int(day))
            
            return None
        except:
            return None
