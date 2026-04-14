# 阿塞拜疆economy爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from datetime import datetime
from news_scraper.items import NewsItem
from news_scraper.utils import get_dynamic_cutoff
from bs4 import BeautifulSoup
import urllib3
import re

# Disable insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class EconomySpider(scrapy.Spider):
    name = 'economy'

    country_code = 'AZE'

    country = '阿塞拜疆'
    allowed_domains = ['economy.gov.az']
    start_urls = ['https://www.economy.gov.az/az/page/media/news']
    
    target_table = 'aze_economy'

    # Azerbaijani month mapping
    AZ_MONTHS = {
        'Yanvar': 1, 'Fevral': 2, 'Mart': 3, 'Aprel': 4,
        'May': 5, 'İyun': 6, 'İyul': 7, 'Avqust': 8,
        'Sentyabr': 9, 'Oktyabr': 10, 'Noyabr': 11, 'Dekabr': 12
    }

    CUTOFF_DATE = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(EconomySpider, cls).from_crawler(crawler, *args, **kwargs)
        spider.CUTOFF_DATE = get_dynamic_cutoff(crawler.settings, spider.target_table, spider_name=spider.name)
        # Ensure we use 2026-01-01 if it's the first run
        if spider.CUTOFF_DATE > datetime(2026, 1, 1):
             spider.CUTOFF_DATE = datetime(2026, 1, 1)
        return spider

    def parse(self, response):
        """Parses the news list page."""
        items = response.css('.news-section__item')
        if not items:
            self.logger.warning(f"No items found on {response.url}")
            return

        article_found = False
        reached_cutoff = False

        for item in items:
            title_node = item.css('.news-section__title')
            date_node = item.css('.news-section__date')
            
            if title_node and date_node:
                title = title_node.xpath('string()').get().strip()
                href = title_node.css('::attr(href)').get()
                date_str = date_node.xpath('string()').get().strip()
                
                publish_time = self.parse_az_date(date_str)
                if not publish_time:
                    continue
                
                if publish_time < self.CUTOFF_DATE:
                    reached_cutoff = True
                    break
                
                article_url = response.urljoin(href)
                yield scrapy.Request(
                    url=article_url,
                    callback=self.parse_detail,
                    meta={'title': title, 'publish_time': publish_time}
                )
                article_found = True

        # Pagination logic
        if not reached_cutoff:
            current_page_match = re.search(r'page=(\d+)', response.url)
            current_page = int(current_page_match.group(1)) if current_page_match else 1
            next_page = current_page + 1
            
            next_page_link = response.css(f'ul.pagination li a[href*="page={next_page}"]::attr(href)').get()
            
            if next_page_link:
                yield response.follow(next_page_link, callback=self.parse)
            elif article_found:
                next_url = f"https://www.economy.gov.az/az/page/media/news?page={next_page}"
                yield scrapy.Request(next_url, callback=self.parse)

    def parse_az_date(self, date_str):
        """Parses Azerbaijani date strings like 'Mart 05, 2026 15:00'."""
        try:
            clean_str = date_str.replace(',', '').replace('  ', ' ')
            parts = clean_str.split(' ')
            if len(parts) >= 4:
                month_name = parts[0]
                day = int(parts[1])
                year = int(parts[2])
                time_parts = parts[3].split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                
                month = self.AZ_MONTHS.get(month_name)
                if month:
                    return datetime(year, month, day, hour, minute)
        except Exception as e:
            self.logger.error(f"Error parsing date {date_str}: {e}")
        return None

    def parse_detail(self, response):
        """Parses the article detail page."""
        item = NewsItem()
        item['url'] = response.url
        item['title'] = response.meta['title']
        item['publish_time'] = response.meta['publish_time']
        item['language'] = 'az'
        item['author'] = 'Ministry of Economy of the Republic of Azerbaijan'
        item['scrape_time'] = datetime.now()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        content_container = soup.select_one('.content-block__text')
        
        if content_container:
            content = content_container.get_text(separator='\n\n', strip=True)
        else:
            p_tags = soup.find_all('p')
            content = '\n\n'.join([p.get_text(strip=True) for p in p_tags if len(p.get_text(strip=True)) > 20])
            
        item['content'] = content.strip()
        yield item
