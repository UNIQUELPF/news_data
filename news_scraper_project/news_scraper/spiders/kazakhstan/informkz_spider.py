import scrapy
from news_scraper.items import InformKzItem
from datetime import datetime
import re
from bs4 import BeautifulSoup
import random
from news_scraper.utils import get_dynamic_cutoff

class InformKzSpider(scrapy.Spider):
    name = 'informkz'
    allowed_domains = ['inform.kz']
    
    # Russian month map
    RU_MONTHS = {
        'Январь': 1, 'Февраль': 2, 'Март': 3, 'Апрель': 4,
        'Май': 5, 'Июнь': 6, 'Июль': 7, 'Август': 8,
        'Сентябрь': 9, 'Октябрь': 10, 'Ноябрь': 11, 'Декабрь': 12
    }
    
    # Months are often displayed in genitive case in Russian dates (e.g. Января)
    # But inform.kz seems to use nominative or abbreviated. Let's handle common cases.
    RU_MONTHS_EXT = {
        'Январь': 1, 'Января': 1,
        'Февраль': 2, 'Февраля': 2,
        'Март': 3, 'Марта': 3,
        'Апрель': 4, 'Апреля': 4,
        'Май': 5, 'Мая': 5,
        'Июнь': 6, 'Июня': 6,
        'Июль': 7, 'Июля': 7,
        'Август': 8, 'Августа': 8,
        'Сентябрь': 9, 'Сентября': 9,
        'Октябрь': 10, 'Октября': 10,
        'Ноябрь': 11, 'Ноября': 11,
        'Декабрь': 12, 'Декабря': 12
    }
    
    CUTOFF_DATE = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(InformKzSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider.CUTOFF_DATE = get_dynamic_cutoff(crawler.settings, 'news_informkz')
        return spider

    def start_requests(self):
        url = 'https://www.inform.kz/category/ekonomika_s1?page=1'
        yield scrapy.Request(
            url,
            meta={
                'playwright': True,
                'playwright_include_page': False,
                'playwright_page_goto_kwargs': {
                    'wait_until': 'domcontentloaded',
                }
            },
            callback=self.parse_list
        )

    def parse_list(self, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        # Based on research, each card is .catpageCard
        articles = soup.select('.catpageCard')
        
        if not articles:
            self.logger.info("No articles found on this page.")
            return

        stop_crawling = False
        current_page = 1
        page_match = re.search(r'page=(\d+)', response.url)
        if page_match:
            current_page = int(page_match.group(1))
        
        for art in articles:
            # Extract date from card div
            # Research showed: "16:37, 29 Январь 2026" inside a div in .catpageCard
            date_div = art.find('div', string=re.compile(r'\d{4}'))
            if not date_div:
                # Try finding div with specific text pattern
                for div in art.find_all('div'):
                    if re.search(r'\d{4}', div.get_text()):
                        date_div = div
                        break
            
            date_text = date_div.get_text(strip=True) if date_div else ""
            publish_date = self.parse_ru_date(date_text)
            
            if publish_date and publish_date < self.CUTOFF_DATE:
                self.logger.info(f"Reached cutoff date {publish_date}. Stopping list parsing.")
                stop_crawling = True
                break
                
            link_el = art.select_one("a[href^='/ru/']")
            if link_el:
                url = response.urljoin(link_el['href'])
                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    meta={
                        'publish_time': publish_date,
                        'playwright': True,
                        'playwright_include_page': False,
                        'playwright_page_goto_kwargs': {'wait_until': 'domcontentloaded'}
                    }
                )

        if not stop_crawling and current_page < 100:
            next_url = f"https://www.inform.kz/category/ekonomika_s1?page={current_page + 1}"
            yield scrapy.Request(
                next_url, 
                callback=self.parse_list,
                meta={
                    'playwright': True,
                    'playwright_include_page': False,
                    'playwright_page_goto_kwargs': {'wait_until': 'domcontentloaded'}
                }
            )

    def parse_ru_date(self, date_str):
        # Format: 16:37, 29 Январь 2026 or variations
        try:
            # Match DD Month YYYY
            match = re.search(r'(\d{1,2})\s+([А-Яа-я]+)\s+(\d{4})', date_str)
            if match:
                day = int(match.group(1))
                month_str = match.group(2)
                year = int(match.group(3))
                month = self.RU_MONTHS_EXT.get(month_str, 1)
                return datetime(year, month, day)
        except Exception as e:
            self.logger.error(f"Error parsing date {date_str}: {e}")
        return None

    def parse_detail(self, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        # Title usually in h1
        title = soup.find('h1').get_text(strip=True) if soup.find('h1') else ""
        
        container = soup.select_one('.article__body-text')
        if not container:
            self.logger.warning(f"Content container not found for {response.url}")
            return

        # Cleaning logic
        # Remove figcaption, img, scripts, styles, and adfox components
        for tag in container.select('script, style, figcaption, img, .adfox, [id*="adfox"]'):
            tag.decompose()
            
        # Extract content from p and blockquote
        text_blocks = []
        for el in container.find_all(['p', 'blockquote']):
            # Preserve blockquote but separate with newlines
            block_text = el.get_text(separator='\n', strip=True)
            if block_text:
                text_blocks.append(block_text)
                
        full_content = "\n\n".join(text_blocks)
        
        item = InformKzItem()
        item['type'] = 'informkz'
        item['title'] = title
        item['url'] = response.url
        item['publish_date'] = response.meta.get('publish_time')
        item['content'] = full_content
        item['crawl_time'] = datetime.now()
        
        yield item
