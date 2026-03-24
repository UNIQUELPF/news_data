import scrapy
from bs4 import BeautifulSoup
import re
from datetime import datetime
from urllib.parse import urljoin
from news_scraper.items import NewsItem
import dateparser

class UaeMubasherSpider(scrapy.Spider):
    name = "uae_mubasher"
    allowed_domains = ["mubasher.info"]
    start_urls = ["https://www.mubasher.info/news/sa/now/latest"]

    target_table = "uae_mubasher"
    LIMIT_DATE = "2026-01-01"

    custom_settings = {
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
    }

    def __init__(self, full_scan='false', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_scan = full_scan.lower() == 'true'
        self.url_seen = set()

    def parse(self, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        
        articles = soup.find_all('div', attrs={'data-title': True})
        
        for a in articles:
            url_path = a.get('data-url')
            if not url_path:
                continue
                
            full_url = urljoin("https://www.mubasher.info", url_path)
            title = a.get('data-title', '').strip()
            
            if full_url in self.url_seen:
                continue
            self.url_seen.add(full_url)
            
            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
                meta={'title': title}
            )

        # Pagination
        current_page = response.meta.get('page', 1)
        if articles:
            next_page = current_page + 1
            next_url = f"https://www.mubasher.info/news/sa/now/latest//{next_page}"
            yield scrapy.Request(
                next_url,
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title = response.meta.get('title')
        if not title:
            h1 = soup.find('h1')
            title = h1.get_text(strip=True) if h1 else ""

        pub_date = None
        time_tag = soup.find('time')
        if time_tag:
            datetime_attr = time_tag.get('datetime')
            if datetime_attr:
                try:
                    dt = dateparser.parse(datetime_attr)
                    if dt:
                        pub_date = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            if not pub_date:
                try:
                    dt = dateparser.parse(time_tag.text.strip())
                    if dt:
                        pub_date = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
        
        if pub_date and not self.full_scan:
            if pub_date[:10] < self.LIMIT_DATE:
                self.logger.info(f"Reached LIMIT_DATE {self.LIMIT_DATE}, stopping at {pub_date}.")
                return
        
        content = ""
        article_body = soup.find('div', class_=lambda c: c and 'article__content-text' in c)
        if not article_body:
            article_body = soup.find('div', class_=lambda c: c and 'mi-article__body' in c)
            
        if article_body:
            content = '\n'.join([p.get_text(strip=True) for p in article_body.find_all('p')])
        
        if not content:
            ps = soup.find_all('p')
            content = '\n'.join([p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 30])
            
        item = NewsItem()
        item['publish_time'] = pub_date or "Unknown"
        item['title'] = title
        item['content'] = content
        item['url'] = response.url
        item['section'] = 'uae_mubasher'
        item['scrape_time'] = datetime.now()
        item['author'] = ""
        item['language'] = "ar"
        
        yield item

