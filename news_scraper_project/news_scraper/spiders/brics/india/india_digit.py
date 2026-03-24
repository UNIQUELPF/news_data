import scrapy
from scrapy.spiders import SitemapSpider
import re
from datetime import datetime
from scrapy.utils.project import get_project_settings
import psycopg2

class IndiaDigitSpider(SitemapSpider):
    name = 'india_digit'
    allowed_domains = ['digit.in']
    
    # Use digit.in's specific news sitemap index
    sitemap_urls = ['https://www.digit.in/sitemaps/news-sitemap.xml']
    
    # Custom pipeline config and batch delays
    custom_settings = {
        'ITEM_PIPELINES': {
            'news_scraper.pipelines.PostgresPipeline': 300,
        },
        'BATCH_SIZE': 500,
        'BATCH_DELAY': 30,
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS': 8,
        'AUTOTHROTTLE_ENABLED': True
    }
    
    target_table = "ind_digit"

    def __init__(self, *args, **kwargs):
        super(IndiaDigitSpider, self).__init__(*args, **kwargs)
        
        # We use a compiled regex catch-all and filter URLs manually in parse_detail
        self.sitemap_rules = [
            (re.compile(r'.*'), 'parse_detail')
        ]
        
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
            self.logger.info(f"Loaded {len(self.seen_urls)} seen URLs from database.")
                
        except Exception as e:
            self.logger.error(f"Database connection error in __init__: {e}")
            self.cutoff_date = datetime(2026, 1, 1)
            self.seen_urls = set()

    def sitemap_filter(self, entries):
        """Filter out old sitemaps if possible to optimize crawling speed"""
        for entry in entries:
            loc = entry.get('loc', '')
            # Filter the main sitemap index containing news-sitemap-month-year.xml
            if 'news-sitemap-' in loc:
                try:
                    # news-sitemap-march-2026.xml -> march 2026
                    match = re.search(r'news-sitemap-([a-z]+)-(\d{4})\.xml', loc)
                    if match:
                        month_str = match.group(1)
                        year_str = match.group(2)
                        # We only need 2026 and newer, or compare exact month/year
                        sitemap_date = datetime.strptime(f"{month_str}-{year_str}", "%B-%Y")
                        
                        cutoff_month = self.cutoff_date.replace(day=1, hour=0, minute=0, second=0)
                        if sitemap_date < cutoff_month:
                            self.logger.debug(f"Skipping old sitemap: {loc}")
                            continue
                except Exception as e:
                    self.logger.debug(f"Error parsing date from sitemap loc {loc}: {e}")
                    
            yield entry

    def parse(self, response):
        """Mandatory callback for SitemapSpider to process all sub-links"""
        yield from self.parse_detail(response)

    def parse_detail(self, response):
        # Prevent non HTML responses
        if not response.url.endswith('.html') or '/news/' not in response.url:
            return
            
        # Skip if already in DB
        if response.url in self.seen_urls:
            return
            
        # Date extraction
        date_el = response.css('meta[property="article:published_time"]::attr(content), meta[name="publish-date"]::attr(content)').get()
        pub_time = None
        if date_el:
            try:
                # "2026-03-16T16:18:00+05:30"
                date_str = date_el.strip()
                date_str = re.sub(r'([+-]\d{2}:\d{2})$', '', date_str).replace('T', ' ').strip()
                if '.' in date_str:
                    date_str = date_str.split('.')[0]
                pub_time = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                self.logger.debug(f"Could not parse date: {date_el}")
        
        # Check against cutoff
        if pub_time and pub_time < self.cutoff_date:
            return
            
        item = {}
        item['url'] = response.url
        
        # Title
        item['title'] = response.css('h1::text').get(default='').strip()
        if not item['title']:
            return # Drop invalid items
            
        item['publish_time'] = pub_time
        item['language'] = 'en'
        
        # Author extraction from JSON-LD or meta or CSS container
        author = None
        try:
            import json
            ld_scripts = response.css('script[type="application/ld+json"]::text').getall()
            for ld_text in ld_scripts:
                try:
                    ld = json.loads(ld_text)
                except:
                    continue
                # jsonld might be a list or exactly a dictionary
                # digit.in wraps multiple schemas or an array
                if isinstance(ld, dict) and 'author' in ld:
                    a = ld['author']
                    if isinstance(a, dict):
                        author = a.get('name', '')
                    elif isinstance(a, str):
                        author = a
                elif isinstance(ld, dict) and '@graph' in ld:
                    for element in ld['@graph']:
                        if element.get('@type') == 'Person' and element.get('name'):
                            author = element.get('name')
                
                if author:
                    break
        except Exception:
            pass
            
        if not author:
            # Fallback CSS
            author = response.css('.author_detail_box a::text, .post-author a::text, [rel="author"]::text').get(default='').strip()
            
        item['author'] = author if author else None
        
        # Content wrappers
        content_parts = response.css('article p::text, article p *::text, .article_content p::text, .entry-content p::text').getall()
             
        # Clean up whitespace and join
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
