import scrapy
import re
import psycopg2
import time
from datetime import datetime
from bs4 import BeautifulSoup
from news_scraper.settings import POSTGRES_SETTINGS

class IranIranIntlSpider(scrapy.Spider):
    name = 'iran_iranintl'
    target_table = 'iran_iranintl'
    allowed_domains = ['iranintl.com']
    
    def __init__(self, full_scan='false', *args, **kwargs):
        super(IranIranIntlSpider, self).__init__(*args, **kwargs)
        self.full_scan = full_scan.lower() == 'true'
        self.conn = psycopg2.connect(**POSTGRES_SETTINGS)
        self.cur = self.conn.cursor()
        self.item_count = 0
        
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS iran_iranintl (
                id SERIAL PRIMARY KEY,
                url VARCHAR UNIQUE,
                title VARCHAR,
                author VARCHAR,
                publish_time TIMESTAMP,
                content TEXT,
                language VARCHAR DEFAULT 'en',
                section VARCHAR DEFAULT 'Economy',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
        
    def start_requests(self):
        # We start with page 1
        yield scrapy.Request('https://www.iranintl.com/en/economy-and-environment', callback=self.parse_list, meta={'page': 1})
        
    def update_item_count(self):
        self.item_count += 1
        if self.item_count % 500 == 0:
            self.logger.info("Reached 500 items, sleeping for 20 seconds...")
            time.sleep(20)

    def parse_list(self, response):
        page = response.meta.get('page', 1)
        
        # Extract article links
        # Links are like /en/202603103882
        link_pattern = re.compile(r'/en/(\d{12})$')
        
        all_links = response.css('a::attr(href)').getall()
        article_links = set()
        for link in all_links:
            match = link_pattern.search(link)
            if match:
                article_links.add(response.urljoin(link))
                
        if not article_links:
            self.logger.info("No more article links found on page %d", page)
            return
            
        continue_crawling = True
        
        for url in article_links:
            # Check date from URL ID if it starts with 2025 or earlier, skip
            match = re.search(r'/en/(\d{4})', url)
            if match:
                year = int(match.group(1))
                if year < 2026:
                    self.logger.info(f"Reached articles from {year}, stopping pagination.")
                    continue_crawling = False
                    continue
            
            # Check incremental
            self.cur.execute("SELECT 1 FROM iran_iranintl WHERE url = %s", (url,))
            if self.cur.fetchone():
                self.logger.info(f"Article already exists: {url}")
                if not self.full_scan:
                    # In incremental mode, if we see existing article, we might want to stop early?
                    # Since it might be mixed, we just skip it. Often in list parsing it means we are caught up.
                    pass
                continue
                
            yield scrapy.Request(url, callback=self.parse_article)
            
        if continue_crawling:
            next_page = page + 1
            next_url = f"https://www.iranintl.com/en/economy-and-environment?page={next_page}"
            yield scrapy.Request(next_url, callback=self.parse_list, meta={'page': next_page})

    def parse_article(self, response):
        soup = BeautifulSoup(response.body, 'html.parser')
        
        title_meta = soup.find("meta", property="og:title")
        title = title_meta["content"].strip() if title_meta else ""
        
        author_meta = soup.find("meta", attrs={"name": "author"})
        author = author_meta["content"].strip() if author_meta else "Iran International"
        
        date_meta = soup.find("meta", property="article:published_time")
        if date_meta and date_meta.get("content"):
            date_str = date_meta["content"]
            try:
                # 2026-03-11T03:05:48.050Z
                date_str_clean = re.sub(r'\.\d+Z$', '', date_str).replace('Z', '')
                publish_time = datetime.strptime(date_str_clean, "%Y-%m-%dT%H:%M:%S")
            except Exception as e:
                self.logger.warning(f"Failed to parse date {date_str}: {e}")
                publish_time = datetime.now()
        else:
            publish_time = datetime.now()
            
        paragraphs = []
        for p in soup.find_all("p"):
            text = p.get_text().strip()
            # simple filter, but might need adjustment
            if len(text) > 40:
                paragraphs.append(text)
                
        content = "\n\n".join(paragraphs)
        
        if not title or not content:
            return

        try:
            self.cur.execute("""
                INSERT INTO iran_iranintl (url, title, author, publish_time, content, language, section)
                VALUES (%s, %s, %s, %s, %s, 'en', 'Economy')
                ON CONFLICT (url) DO NOTHING
            """, (response.url, title, author, publish_time, content))
            self.conn.commit()
            self.logger.info(f"Saved to DB: {response.url}")
            self.update_item_count()
            
            yield {
                'url': response.url,
                'title': title,
                'author': author,
                'publish_time': publish_time,
                'content': content, 'language': 'en', 'section': 'Economy'
            }
        except Exception as e:
            self.conn.rollback()
            self.logger.error(f"Error saving {response.url}: {e}")
            
    def close(self, reason):
        self.cur.close()
        self.conn.close()
