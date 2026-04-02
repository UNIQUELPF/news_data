# 阿联酋fxnewstoday爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from bs4 import BeautifulSoup
import re
from datetime import datetime
from urllib.parse import urljoin
from news_scraper.items import NewsItem

class UaeFxNewsTodaySpider(scrapy.Spider):
    name = "uae_fxnewstoday"
    allowed_domains = ["fxnewstoday.ae"]
    start_urls = ["https://www.fxnewstoday.ae/latest-news"]
    
    target_table = "uae_fxnewstoday"

    LIMIT_DATE = "2026-01-01"

    custom_settings = {
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
    }

    def __init__(self, full_scan='false', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_scan = str(full_scan).lower() in ['true', '1', 'yes']
        self.url_seen = set()
        self.limit_date = self._get_db_cutoff()
        
    def _get_db_cutoff(self):
        try:
            from news_scraper.settings import POSTGRES_SETTINGS
            import psycopg2
            
            conn = psycopg2.connect(**POSTGRES_SETTINGS)
            cur = conn.cursor()
            
            cur.execute(f"CREATE TABLE IF NOT EXISTS {self.target_table} (" 
                        "id SERIAL PRIMARY KEY, "
                        "url VARCHAR(500) UNIQUE, "
                        "title VARCHAR(500), "
                        "content TEXT, "
                        "publish_time VARCHAR(100), "
                        "author VARCHAR(255), "
                        "language VARCHAR(50), "
                        "section VARCHAR(100) DEFAULT 'uae_fxnewstoday', "
                        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                        ")")
            conn.commit()
            
            cur.execute(
                f"""
                SELECT MAX(
                    CASE
                        WHEN publish_time ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}'
                        THEN publish_time
                        ELSE NULL
                    END
                )
                FROM {self.target_table}
                """
            )
            max_date = cur.fetchone()[0]
            cur.close()
            conn.close()

            if self.full_scan or not max_date:
                return self.LIMIT_DATE
            else:
                return str(max_date)[:10]
        except Exception as e:
            self.logger.error(f"Database error during INIT: {e}")
            return self.LIMIT_DATE

    def _extract_publish_time(self, text):
        if not text:
            return None
        dt_match = re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}', text)
        if dt_match:
            return dt_match.group(0)
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', text)
        if date_match:
            return date_match.group(0)
        return None

    def parse(self, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Extract articles
        items = soup.find_all('a', href=re.compile(r'-\d{5,8}$'))
        for item in items:
            url = item.get('href')
            if not url:
                continue
            
            full_url = urljoin("https://www.fxnewstoday.ae", url)
            
            if full_url in self.url_seen:
                continue
            self.url_seen.add(full_url)
            
            # Find the parent wrapper to extract date
            parent = item.find_parent('div', class_=lambda c: c and ('mb-2' in c or 'card' in c or 'article' in c or 'news-item' in c))
            if not parent:
                parent = item.parent.parent
            
            text = parent.get_text(separator=' ', strip=True) if parent else ""
            pub_date = self._extract_publish_time(text)
            
            # Incremental check based on date
            if not self.full_scan and pub_date:
                if pub_date[:10] < self.limit_date:
                    self.logger.info(f"Reached limit_date {self.limit_date}, stopping at {pub_date}.")
                    return
            
            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
                meta={'pub_date': pub_date}
            )

        # 2. Extract next page ONLY if we didn't return early
        load_more = soup.find('button', id='LoadMoreBtn')
        if load_more and load_more.get('data-cursor'):
            next_url = load_more.get('data-cursor')
            if next_url and not next_url.startswith('http'):
                next_url = urljoin("https://www.fxnewstoday.ae", next_url)
            
            yield scrapy.Request(
                next_url,
                callback=self.parse
            )

    def parse_article(self, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else ""
        if not title and soup.title:
            title = soup.title.get_text(strip=True).split('|')[0].strip()
        
        pub_date = response.meta.get('pub_date')
        if not pub_date:
            pub_date = self._extract_publish_time(soup.get_text(separator=' ', strip=True))
            
        content = ""
        # Sometimes content sits inside <div class="article-content" ...>
        desc_span = soup.find('span', class_=lambda c: c and 'desc-text' in c)
        if desc_span:
            content = desc_span.get_text(separator='\n', strip=True)

        article_body = soup.find('div', class_=lambda c: c and 'content' in c.lower() and 'article' in c.lower())
        if not content and article_body:
            content = '\n'.join([p.get_text(strip=True) for p in article_body.find_all('p')])
            if not content:
                content = article_body.get_text(separator='\n', strip=True)
        elif not content:
            ps = soup.find_all('p')
            content = '\n'.join([p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 30])
        
        # In case no paragraph but standard body div
        if not content:
            body = soup.find('div', itemprop="articleBody")
            if body:
                content = body.get_text(separator='\n', strip=True)

        if not content:
            self.logger.warning(f"No content found for {response.url}")
            return
            
        if not self.full_scan and pub_date and pub_date < self.limit_date:
            return

        item = NewsItem()
        item['publish_time'] = pub_date
        item['title'] = title
        item['content'] = content
        item['url'] = response.url
        item['section'] = 'uae_fxnewstoday'
        item['scrape_time'] = datetime.now()
        item['author'] = ""
        item['language'] = "ar"
        
        yield item
