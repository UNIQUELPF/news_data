# 塞尔维亚danas爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
import re
from datetime import datetime
from news_scraper.items import NewsItem
from news_scraper.utils import get_dynamic_cutoff
from bs4 import BeautifulSoup

class DanasSpider(scrapy.Spider):
    name = 'danas'
    allowed_domains = ['danas.rs']
    start_urls = [
        'https://www.danas.rs/vesti/ekonomija/',
        'https://www.danas.rs/rubrika/vesti/ekonomija/',
        'https://www.danas.rs/rubrika/svet/'
    ]
    
    target_table = 'ser_danas'

    # Serbian month mapping (genitive case)
    SR_MONTHS = {
        'januara': 1, 'februara': 2, 'marta': 3, 'aprila': 4,
        'maja': 5, 'juna': 6, 'jula': 7, 'avgusta': 8,
        'septembra': 9, 'oktobra': 10, 'novembra': 11, 'decembra': 12
    }

    CUTOFF_DATE = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(DanasSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider.CUTOFF_DATE = get_dynamic_cutoff(crawler.settings, spider.target_table)
        return spider

    def parse(self, response):
        """Parses the news list page."""
        headers = response.css('h3.article-post-title')
        self.logger.info(f"Scraping {len(headers)} articles from {response.url}")

        reached_cutoff = False
        article_found_count = 0

        for header in headers:
            title_node = header.css('a')
            if not title_node:
                title_node = header if header.root.tag == 'a' else None
                
            if not title_node:
                continue
                
            title = title_node.xpath('string()').get().strip()
            href = title_node.css('::attr(href)').get()
            
            date_node = header.xpath('./preceding::span[contains(@class, "published")][1]')
            if not date_node:
                date_node = header.xpath('ancestor::article//span[contains(@class, "published")]')
            
            if date_node:
                date_str = date_node.xpath('string()').get().strip()
                date_str = date_str.replace('•', '').strip()
                publish_time = self.parse_sr_date(date_str)
                
                if publish_time:
                    if publish_time < self.CUTOFF_DATE:
                        reached_cutoff = True
                        self.logger.info(f"Reached cutoff date {self.CUTOFF_DATE} at {publish_time}. Stopping.")
                        break
                    
                    article_url = response.urljoin(href)
                    yield scrapy.Request(
                        url=article_url,
                        callback=self.parse_detail,
                        meta={'title': title, 'publish_time': publish_time}
                    )
                    article_found_count += 1

        self.logger.info(f"Scraped {article_found_count} articles from {response.url}")
        if not reached_cutoff:
            next_page = response.css('a.next.page-numbers::attr(href)').get()
            if next_page:
                yield response.follow(next_page, callback=self.parse)

    def parse_sr_date(self, date_str):
        """Parses Serbian date strings like '05.03.2026. 15:20' or 'danas 10:36'."""
        now = datetime.now()
        try:
            if 'danas' in date_str.lower():
                time_match = re.search(r'(\d{2}):(\d{2})', date_str)
                if time_match:
                    return now.replace(hour=int(time_match.group(1)), minute=int(time_match.group(2)), second=0, microsecond=0)
            
            date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})\.\s+(\d{2}):(\d{2})', date_str)
            if date_match:
                day = int(date_match.group(1))
                month = int(date_match.group(2))
                year = int(date_match.group(3))
                hour = int(date_match.group(4))
                minute = int(date_match.group(5))
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
        item['language'] = 'sr'
        item['author'] = 'Danas.rs'
        item['scrape_time'] = datetime.now()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        content_container = soup.select_one('.article-content')
        
        if content_container:
            p_tags = content_container.find_all('p')
            content = '\n\n'.join([p.get_text(strip=True) for p in p_tags if len(p.get_text(strip=True)) > 10])
            if not content:
                content = content_container.get_text(separator='\n\n', strip=True)
        else:
            p_tags = soup.find_all('p')
            content = '\n\n'.join([p.get_text(strip=True) for p in p_tags if len(p.get_text(strip=True)) > 20])
            
        item['content'] = content.strip()
        yield item
