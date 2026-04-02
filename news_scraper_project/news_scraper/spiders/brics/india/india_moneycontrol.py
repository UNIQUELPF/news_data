# 印度moneycontrol爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from scrapy.spiders import SitemapSpider
from datetime import datetime
from scrapy.exceptions import DropItem
import json
from news_scraper.items import NewsItem

class IndiaMoneycontrolSpider(SitemapSpider):
    name = "india_moneycontrol"
    allowed_domains = ["moneycontrol.com"]
    target_table = "ind_moneycontrol"

    # Use the 2026 sitemap containing all post links
    sitemap_urls = ['https://www.moneycontrol.com/news/index-sitemap-2026.xml']
    
    # Only follow economy urls to avoid scraping everything on the site
    sitemap_rules = [
        ('/news/business/economy/', 'parse_detail'),
    ]

    def __init__(self, *args, **kwargs):
        super(IndiaMoneycontrolSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime(2026, 1, 1)
        
        # Connect to Postgres to instantiate the table and find latest date (incremental support)
        try:
            import psycopg2
            from scrapy.utils.project import get_project_settings
            settings = get_project_settings()
            pg = settings.get('POSTGRES_SETTINGS', {})
            conn = psycopg2.connect(
                host=pg.get('host', 'postgres'),
                database=pg.get('database', 'scrapy_db'),
                user=pg.get('user', 'your_user'),
                password=pg.get('password', 'your_password'),
                port=pg.get('port', 5432)
            )
            cur = conn.cursor()
            # Create table if it doesn't exist
            cur.execute(f"CREATE TABLE IF NOT EXISTS {self.target_table} (id SERIAL PRIMARY KEY, url TEXT UNIQUE, title TEXT, content TEXT, publish_time TIMESTAMP, author TEXT, language TEXT);")
            conn.commit()

            cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            row = cur.fetchone()
            if row and row[0]:
                self.cutoff_date = max(self.cutoff_date, row[0].replace(tzinfo=None))
            conn.close()
            self.logger.info(f"Using cutoff date: {self.cutoff_date}")
        except Exception as e:
            self.logger.warning(f"Error fetching max date from DB: {e}")

    # Optionally filter out older sitemap links to save bandwidth
    def sitemap_filter(self, entries):
        for entry in entries:
            lastmod = entry.get('lastmod')
            if lastmod and '2025' in lastmod:
                continue
            yield entry

    def parse_detail(self, response):
        item = NewsItem()
        item['url'] = response.url
        item['language'] = 'English'
        
        # Title
        item['title'] = (response.css('h1.article_title::text').get() or "").strip()
        
        # Publish Time
        pub_time = None
        date_str = response.css('meta[property="og:article:published_time"]::attr(content)').get()
        if date_str:
            try:
                pub_time = datetime.fromisoformat(date_str).replace(tzinfo=None)
            except Exception as e:
                self.logger.error(f"Failed to parse article date: {e}")
        
        item['publish_time'] = pub_time
        
        # On a Sitemap spider, we shouldn't DropItem and kill the spider just because we hit one old article,
        # because the sitemap doesn't guarantee strict reverse chronological order across all index files.
        # Instead, we just yield nothing and 'ignore' old items.
        if pub_time and pub_time < self.cutoff_date:
            return  # Skip yielding this item, let spider continue reading XML

        # Content
        content_parts = response.css('.content_wrapper p::text, .content_wrapper p *::text').getall()
        item['content'] = "\n".join([p.strip() for p in content_parts if p.strip()])
        
        # Author
        author = response.css('.article_author::text').get(default='').strip()
        if not author:
            author = response.css('.article_author span::text').get(default='').strip()
        item['author'] = author or "Moneycontrol"

        if not item['title'] or not item['content']:
            return

        yield item
