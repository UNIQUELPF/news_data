# 埃及cbe爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
import re
from datetime import datetime
import psycopg2
from scrapy.utils.project import get_project_settings
from news_scraper.items import NewsItem
from w3lib.html import remove_tags

class EgyptCbeSpider(scrapy.Spider):
    name = "egypt_cbe"
    allowed_domains = ["cbe.org.eg"]
    target_table = "egy_cbe"
    start_urls = ["https://www.cbe.org.eg/sitemap.xml"]
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DEFAULT_REQUEST_HEADERS': {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8", # include Arabic in Accept-Language
            "Sec-Ch-Ua": "\"Chromium\";v=\"122\", \"Not(A:Brand\";v=\"24\", \"Google Chrome\";v=\"122\"",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate"
        }
    }

    def __init__(self, *args, **kwargs):
        super(EgyptCbeSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = getattr(self, 'start_date', datetime(2026, 1, 1))
        self.seen_urls = set()
        
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(EgyptCbeSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider._init_db()
        return spider
        
    def _init_db(self):
        settings = get_project_settings()
        db_settings = settings.get('POSTGRES_SETTINGS')
        if not db_settings:
            return

        try:
            conn = psycopg2.connect(
                host=db_settings['host'],
                dbname=db_settings['dbname'],
                user=db_settings['user'],
                password=db_settings['password'],
                port=db_settings['port']
            )
            cur = conn.cursor()
            
            # Create table if not exists
            cur.execute('''
                CREATE TABLE IF NOT EXISTS egy_cbe (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(500),
                    publish_time TIMESTAMP,
                    author VARCHAR(255),
                    content TEXT,
                    url VARCHAR(500) UNIQUE,
                    language VARCHAR(10),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Fetch max date for incremental logic
            cur.execute('SELECT MAX(publish_time) FROM egy_cbe')
            max_date = cur.fetchone()[0]
            if max_date:
                self.cutoff_date = max_date
                self.logger.info(f"Initialized cutoff date from DB: {self.cutoff_date}")
            else:
                self.logger.info(f"No existing data, using default cutoff: {self.cutoff_date}")

            # Pre-load seen URLs to optimize
            cur.execute('SELECT url FROM egy_cbe')
            for row in cur.fetchall():
                self.seen_urls.add(row[0])
                
            conn.commit()
            cur.close()
            conn.close()
            
        except psycopg2.Error as e:
            self.logger.error(f"Database error during initialization: {e}")

    def parse(self, response):
        # Extract loc elements using regex to avoid xml parsing issues with namespaces
        xml = response.text
        urls = re.findall(r'<loc>(.*?)</loc>', xml)
        self.logger.info(f"Found {len(urls)} total URLs in sitemap")
        
        news_urls = [u for u in urls if '/news-publications/news/' in u]
        self.logger.info(f"Filtered down to {len(news_urls)} news URLs")
        
        passed = 0
        for url in news_urls:
            # We enforce scraping both /en/ and /ar/ articles
            if url in self.seen_urls:
                continue

            match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/(\d{2})/(\d{2})/', url)
            if match:
                dt_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)} {match.group(4)}:{match.group(5)}:00"
                pub_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            else:
                match2 = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
                if match2:
                    pub_time = datetime(int(match2.group(1)), int(match2.group(2)), int(match2.group(3)))
                else:
                    continue
                    
            if pub_time >= self.cutoff_date:
                passed += 1
                yield scrapy.Request(
                    url, 
                    callback=self.parse_article,
                    meta={'publish_time': pub_time}
                )
                
        self.logger.info(f"Yielded {passed} article requests matching delta rules since {self.cutoff_date}")

    def parse_article(self, response):
        pub_time = response.meta['publish_time']
        
        # Double check it safely
        if pub_time < self.cutoff_date:
            return

        title_css = response.css('h1::text, .article-title::text, .cbe-title::text, h2::text')
        title = title_css.get()
        if title:
            title = title.strip()
        
        author = "Central Bank of Egypt"
        
        # Extract content
        p_elements = response.css('.cbe-rich-text p, .content p, .details p, article p, .news-details p, #main-content p')
        if not p_elements:
            # aggressive fallback
            p_elements = response.css('p')
            
        paragraphs = []
        for p in p_elements:
            text = remove_tags(p.get()).strip()
            text = re.sub(r'\s+', ' ', text)
            if text and len(text) > 10:
                paragraphs.append(text)
                
        content = "\n\n".join(paragraphs)
        if not content:
            return
            
        item = {
            'title': title or "CBE News",
            'publish_time': pub_time,
            'author': author,
            'content': content,
            'url': response.url,
            'language': 'ar' if '/ar/' in response.url else 'en'
        }
        yield item
        
