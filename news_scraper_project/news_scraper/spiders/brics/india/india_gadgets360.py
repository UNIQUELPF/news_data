import scrapy
from datetime import datetime
import psycopg2
from scrapy.utils.project import get_project_settings
import re
import json

from scrapy.spiders import SitemapSpider

class IndiaGadgets360Spider(SitemapSpider):
    name = 'india_gadgets360'
    allowed_domains = ['gadgets360.com']
    sitemap_urls = ['https://www.gadgets360.com/sitemapnews.xml', 'https://www.gadgets360.com/sitemaps/news-sitemap.xml']

    
    use_curl_cffi = True
    # Custom pipeline config and batch delays
    custom_settings = {
        'ITEM_PIPELINES': {
            'news_scraper.pipelines.PostgresPipeline': 300,
        },
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 50,
        },
        'BATCH_SIZE': 500,
        'BATCH_DELAY': 30,
        'DOWNLOAD_DELAY': 2, # Higher delay to avoid WAF block
        'CONCURRENT_REQUESTS': 2,
        'AUTOTHROTTLE_ENABLED': True
    }
    
    target_table = "ind_gadgets360"

    def __init__(self, *args, **kwargs):
        super(IndiaGadgets360Spider, self).__init__(*args, **kwargs)
        
        settings = get_project_settings()
        db_settings = settings.get('POSTGRES_SETTINGS', {})
        
        try:
            self.conn = psycopg2.connect(
                host=db_settings.get('host', 'postgres'),
                database=db_settings.get('database', 'scrapy_db'),
                user=db_settings.get('user', 'your_user'),
                password=db_settings.get('password', 'your_password'),
                port=db_settings.get('port', 5432)
            )
            self.cur = self.conn.cursor()
            
            # Create table if it doesn't exist
            self.cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.target_table} (
                    id SERIAL PRIMARY KEY,
                    url VARCHAR UNIQUE NOT NULL,
                    title VARCHAR NOT NULL,
                    content TEXT,
                    publish_time TIMESTAMP,
                    author VARCHAR,
                    language VARCHAR(10) DEFAULT 'en',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.commit()
            
            # Get the latest publish time to only fetch new articles
            self.cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            result = self.cur.fetchone()
            if result and result[0]:
                self.cutoff_date = result[0]
                self.logger.info(f"Incremental scraping starting from cutoff date: {self.cutoff_date}")
            else:
                self.cutoff_date = datetime(2026, 1, 1)
                self.logger.info(f"Initial run, starting from default cutoff date: {self.cutoff_date}")
                
            # Pre-load seen URLs
            self.cur.execute(f"SELECT url FROM {self.target_table}")
            self.seen_urls = set(row[0] for row in self.cur.fetchall())
                
        except Exception as e:
            self.logger.error(f"Database connection error: {e}")
            self.cutoff_date = datetime(2026, 1, 1)
            self.seen_urls = set()

    def parse(self, response):
        if response.url in self.seen_urls:
            return
            
        # Parse data from JSON-LD which Gadgets360 reliably embeds
        date_str = None
        author = None
        
        try:
            ld_scripts = response.css('script[type="application/ld+json"]::text').getall()
            for text in ld_scripts:
                try:
                    data = json.loads(text)
                except:
                    continue
                    
                if isinstance(data, dict):
                    # Article schema
                    if 'datePublished' in data:
                        date_str = data.get('datePublished')
                    if 'author' in data:
                        a = data['author']
                        if isinstance(a, list) and len(a) > 0:
                            author = a[0].get('name')
                        elif isinstance(a, dict):
                            author = a.get('name')
                        elif isinstance(a, str):
                            author = a
                            
                elif isinstance(data, list):
                    for item in data:
                        if 'datePublished' in item:
                            date_str = item.get('datePublished')
                if date_str:
                    break
        except Exception:
            pass

        # Parse date
        pub_time = None
        if not date_str:
            date_str = response.css('meta[itemprop="datePublished"]::attr(content), meta[property="article:published_time"]::attr(content)').get()
            
        if date_str:
            try:
                # Format: 2026-03-16T12:00:00+05:30
                clean_date = re.sub(r'([+-]\d{2}:\d{2})$', '', date_str).replace('T', ' ').strip()
                if '.' in clean_date:
                    clean_date = clean_date.split('.')[0]
                pub_time = datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                self.logger.debug(f"Could not parse date: {date_str}")
                
        if pub_time and (pub_time < self.cutoff_date):
            return

        item = {}
        item['url'] = response.url
        
        # Title
        item['title'] = response.css('h1::text').get(default='').strip()
        if not item['title']:
            return
            
        item['publish_time'] = pub_time
        item['language'] = 'en'
        
        # Author fallback
        if not author:
            author = response.css('.author_name a::text, .byline a::text').get(default='').strip()
        item['author'] = author if author else None
        
        # Content
        content_parts = response.css('.content_text p::text, .content_text p *::text, #article_content p::text, .story_content p::text').getall()
        
        cleaned_parts = []
        for p in content_parts:
            text = p.strip()
            if text and len(text) > 1 and "{" not in text:
                cleaned_parts.append(text)
                
        if not cleaned_parts:
            return
            
        item['content'] = "\n".join(cleaned_parts)
        
        yield item

    def closed(self, reason):
        if hasattr(self, 'cur'):
            self.cur.close()
        if hasattr(self, 'conn'):
            self.conn.close()
