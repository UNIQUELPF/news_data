import scrapy
import json
import psycopg2
from datetime import datetime
import dateutil.parser
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.items import NewsItem

class EnanyangSpider(scrapy.Spider):
    name = "malaysia_enanyang"
    allowed_domains = ["enanyang.my"]
    target_table = "malaysia_enanyang_news"
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.5,
    }

    # cat=2 corresponds to 财经 (Finance)
    CATEGORIES = [
        {'id': 2, 'name': 'Finance'}
    ]

    def __init__(self, start_date=None, *args, **kwargs):
        super(EnanyangSpider, self).__init__(*args, **kwargs)
        if start_date:
            self.cutoff_date = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            self.cutoff_date = self.get_latest_db_date()
        self.logger.info(f"Using cutoff: {self.cutoff_date}")
        self.init_db()

    def get_latest_db_date(self):
        try:
            conn = psycopg2.connect(**POSTGRES_SETTINGS)
            cur = conn.cursor()
            cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{self.target_table}')")
            if not cur.fetchone()[0]:
                return datetime(2026, 1, 1)

            cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            res = cur.fetchone()[0]
            cur.close()
            conn.close()
            if res:
                return res.replace(tzinfo=None)
        except Exception as e:
            self.logger.warning(f"Failed to get max date from DB, defaulting to 2026-01-01: {e}")
        return datetime(2026, 1, 1)

    def init_db(self):
        try:
            conn = psycopg2.connect(**POSTGRES_SETTINGS)
            cur = conn.cursor()
            cur.execute(f"CREATE TABLE IF NOT EXISTS {self.target_table} (url TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT, publish_time TIMESTAMP NOT NULL, author VARCHAR(255), language VARCHAR(50), section VARCHAR(100), scraped_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            self.logger.error(f"Failed to init table: {e}")

    async def start(self):
        for cat in self.CATEGORIES:
            # offset starts at 0, pagenum starts at 1
            url = f"https://www.enanyang.my/api/category-posts?cat={cat['id']}&offset=0&pagenum=1&excludeids="
            yield scrapy.Request(url, callback=self.parse_list, meta={'cat': cat, 'page': 1})

    def parse_list(self, response):
        cat = response.meta['cat']
        page = response.meta['page']
        
        try:
            items = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
            return
            
        if not items or not isinstance(items, list):
            self.logger.info(f"No items found on page {page} for category {cat['name']}")
            return
            
        self.logger.info(f"Page {page} for {cat['name']}: found {len(items)} items")
            
        oldest_on_page = None
        
        for item in items:
            title = item.get('title')
            url = item.get('permalink')
            pub_date_str = item.get('post_date') # Format: "2026-03-25 12:58:42"
            
            if not pub_date_str:
                continue
                
            try:
                dt = datetime.strptime(pub_date_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
                
            if oldest_on_page is None or dt < oldest_on_page:
                oldest_on_page = dt
                
            if dt >= self.cutoff_date:
                yield scrapy.Request(
                    url, 
                    callback=self.parse_article,
                    meta={
                        'title': title,
                        'publish_time': dt,
                        'section': cat['name']
                    }
                )
                
        # Pagination
        if oldest_on_page and oldest_on_page >= self.cutoff_date:
            next_page = page + 1
            # Using offset=0 as pagenum already handles skipping. 
            # Combining both often leads to double skipping on this site.
            next_url = f"https://www.enanyang.my/api/category-posts?cat={cat['id']}&offset=0&pagenum={next_page}&excludeids="
            yield scrapy.Request(next_url, callback=self.parse_list, meta={'cat': cat, 'page': next_page})
        else:
            self.logger.info(f"Reached cutoff or end of content for {cat['name']} at page {page}")

    def parse_article(self, response):
        title = response.meta['title']
        publish_time = response.meta['publish_time']
        section = response.meta['section']
        
        # Content selectors
        # The main body text is in .article-page-post-content and .article-content-more-wrapper
        # We use string(.) to get all text including nested tags
        paragraphs = []
        content_nodes = response.xpath('//div[contains(@class, "article-page-post-content")]//p | //div[contains(@class, "article-content-more-wrapper")]//p')
        
        for node in content_nodes:
            text = node.xpath('string(.)').get()
            if text:
                text = text.strip()
                if text and text not in paragraphs:
                    paragraphs.append(text)
        
        content_text = "\n\n".join(paragraphs)
        
        if not content_text:
            self.logger.warning(f"No content extracted for {response.url}")
            # Fallback but without skipping
            content_text = response.css('.article-page-post-content ::text').getall()
            content_text = "\n".join([t.strip() for t in content_text if t.strip()])

        item = NewsItem()
        item['title'] = title
        item['url'] = response.url
        item['publish_time'] = publish_time.strftime("%Y-%m-%d %H:%M:%S")
        item['author'] = "" 
        item['content'] = content_text
        item['section'] = section
        item['language'] = "zh" # Chinese site
        
        yield item
