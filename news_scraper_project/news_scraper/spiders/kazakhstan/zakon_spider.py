# 哈萨克斯坦zakon spider爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.items import ZakonItem
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
import asyncio
from news_scraper.utils import get_dynamic_cutoff

RU_MONTHS = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
    'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
    'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
}

class ZakonSpider(scrapy.Spider):
    name = 'zakon'
    allowed_domains = ['zakon.kz']
    start_urls = ['https://www.zakon.kz/finansy/']

    CUTOFF_DATE = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(ZakonSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider.CUTOFF_DATE = get_dynamic_cutoff(crawler.settings, 'news_zakon')
        return spider

    def parse_russian_date(self, date_str):
        """Converts Zakon.kz date strings to datetime objects."""
        now = datetime.now()
        date_str = date_str.lower().strip()
        
        if "сегодня" in date_str:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if "вчера" in date_str:
            return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        match = re.search(r"(\d{1,2})\s+([а-я]+)(?:\s+(\d{4}))?", date_str)
        if match:
            day = int(match.group(1))
            month_str = match.group(2)
            year = int(match.group(3)) if match.group(3) else now.year
            
            month = RU_MONTHS.get(month_str)
            if month:
                return datetime(year, month, day)
                
        return None

    def start_requests(self):
        url = "https://www.zakon.kz/finansy/"
        yield scrapy.Request(
            url,
            meta={
                'playwright': True,
                'playwright_include_page': True,
                'playwright_page_goto_kwargs': {
                    'wait_until': 'domcontentloaded',
                    'timeout': 60000,
                }
            },
            callback=self.parse_list
        )

    async def parse_list(self, response):
        page = response.meta['playwright_page']
        
        news_list = []
        stop_crawling = False
        cutoff_date = self.CUTOFF_DATE
        
        attempts = 0
        while attempts < 150:
            # Scroll down
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            
            # Extract current cards
            cards_html = await page.content()
            soup = BeautifulSoup(cards_html, 'html.parser')
            links = soup.select('a.newscard_link')
            self.logger.debug(f"Found {len(links)} newscard_link elements")
            
            for link in links:
                title_el = link.select_one('.newscard__title')
                date_el = link.select_one('.newscard__dateline')
                
                if not title_el or not date_el:
                    self.logger.debug("Missing title or date element in link")
                    continue
                
                title = title_el.get_text(strip=True)
                date_str = date_el.get_text(strip=True)
                href = link.get('href')
                full_url = f"https://www.zakon.kz{href}" if href.startswith('/') else href
                
                parsed_date = self.parse_russian_date(date_str)
                if parsed_date:
                    if parsed_date < cutoff_date:
                        self.logger.info(f"Reached cutoff date: {parsed_date}. Stopping scroll.")
                        stop_crawling = True
                        break
                    
                    if not any(item['url'] == full_url for item in news_list):
                        news_list.append({
                            "title": title,
                            "date": parsed_date,
                            "url": full_url
                        })
                else:
                    self.logger.debug(f"Failed to parse date: {date_str}")
            
            if stop_crawling:
                break
                
            attempts += 1
            self.logger.info(f"Attempt {attempts}: Collected {len(news_list)} items so far...")

        await page.close()

        # Now yield requests for detail pages
        for item in news_list:
            yield scrapy.Request(
                item['url'],
                callback=self.parse_detail,
                meta={'item_data': item}
            )

    def parse_detail(self, response):
        item_data = response.meta['item_data']
        soup = BeautifulSoup(response.text, 'html.parser')
        
        content_div = soup.select_one('div.content')
        clean_text = ""
        if content_div:
            # Cleaning
            for s in content_div.select('script, style, .articleAdver, .social-buttons, .related-news'):
                s.decompose()
            
            # Extract clean text from paragraphs
            paragraphs = [p.get_text(strip=True) for p in content_div.find_all('p')]
            clean_text = "\n\n".join([p for p in paragraphs if p])
        
        item = ZakonItem()
        item['type'] = 'zakon'
        item['title'] = item_data['title']
        item['url'] = item_data['url']
        item['publish_date'] = item_data['date'].strftime("%Y-%m-%d")
        item['content'] = clean_text
        item['crawl_time'] = datetime.now()
        
        yield item
