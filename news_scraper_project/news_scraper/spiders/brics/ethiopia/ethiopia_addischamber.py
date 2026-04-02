# 埃塞俄比亚addischamber爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from datetime import datetime
import psycopg2
import dateparser
from bs4 import BeautifulSoup
import re

from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS

class EthiopiaAddisChamberSpider(scrapy.Spider):
    name = "ethiopia_addischamber"
    allowed_domains = ["addischamber.com"]
    target_table = "ethi_addischamber"
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
    }

    def __init__(self, *args, **kwargs):
        super(EthiopiaAddisChamberSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = self._init_db()
        self.logger.info(f"Spider initialized. Cutoff date set to: {self.cutoff_date}")
        self.scraped_urls = set()

    def _init_db(self):
        try:
            db_settings = POSTGRES_SETTINGS.copy()
            if 'database' in db_settings:
                db_settings['dbname'] = db_settings.pop('database')
            elif 'db' in db_settings:
                db_settings['dbname'] = db_settings.pop('db')
                
            conn = psycopg2.connect(**db_settings)
            cur = conn.cursor()
            
            cur.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.target_table} (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(500),
                    publish_time TIMESTAMP,
                    author VARCHAR(255),
                    content TEXT,
                    url VARCHAR(500) UNIQUE,
                    language VARCHAR(50),
                    section VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            
            cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            max_date = cur.fetchone()[0]
            
            cur.close()
            conn.close()
            
            if max_date:
                return max_date
            return datetime(2026, 1, 1)
        except Exception as e:
            self.logger.error(f"Database init error: {e}")
            return datetime(2026, 1, 1)

    def start_requests(self):
        base_url = "https://addischamber.com/news/"
        yield scrapy.Request(
            url=base_url,
            callback=self.parse_list,
            meta={'page': 1, 'base_url': base_url}
        )

    def parse_list(self, response):
        page = response.meta['page']
        has_older_articles = False
        new_items_found = 0
        
        blocks = response.css('div.ultp-block-item')
        if not blocks:
            # Fallback wrapper
            blocks = response.css('article')
            
        for block in blocks:
            # Try getting title block first or any A tag
            a_tag = block.css('h3 a, .ultp-block-title a, h2 a')
            if not a_tag:
                a_tag = block.css('a')
                
            if not a_tag:
                continue
                
            url_fragment = a_tag.attrib.get('href')
            if not url_fragment:
                continue
                
            full_url = response.urljoin(url_fragment)
            if full_url in self.scraped_urls:
                continue
            self.scraped_urls.add(full_url)
            
            # Get date
            date_str = None
            text_content = block.xpath('.//text()').getall()
            for txt in text_content:
                txt = txt.strip()
                if re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, 20\d\d', txt):
                    date_str = txt
                    break
            
            pub_time = None
            if date_str:
                parsed = dateparser.parse(date_str, settings={'TIMEZONE': 'UTC'})
                if parsed:
                    pub_time = parsed
                    
            if pub_time and pub_time.replace(tzinfo=None) < self.cutoff_date.replace(tzinfo=None):
                self.logger.debug(f"Article older than cutoff: {full_url}")
                has_older_articles = True
                continue
                
            new_items_found += 1
            yield scrapy.Request(
                url=full_url,
                callback=self.parse_article,
                meta={'pub_time': pub_time}
            )

        # Pagination
        if not has_older_articles and new_items_found > 0:
            next_page = page + 1
            next_url = f"https://addischamber.com/news/page/{next_page}/"
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_list,
                meta={'page': next_page}
            )
        else:
            self.logger.info("Cutoff reached or no new items found. Stop pagination.")

    def parse_article(self, response):
        title = response.css('h1::text, h1.entry-title::text, .elementor-heading-title::text').get()
        if not title:
            # try finding h1 anyway with soup inside scrapy logic or any title block
            title = response.css('title::text').get()
            if title:
                title = title.split('|')[0].strip()
        if not title:
            self.logger.warning(f"No title found for {response.url}")
            return
        title = title.strip()

        pub_time = response.meta.get('pub_time')
        if not pub_time:
            # Fallback english date on page
            content_texts = response.xpath('//text()').getall()
            for txt in content_texts:
                match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, 20\d\d', txt.strip())
                if match:
                    parsed = dateparser.parse(match.group(), settings={'TIMEZONE': 'UTC'})
                    if parsed:
                        pub_time = parsed
                        break
            if not pub_time:
                pub_time = datetime.now()
                
        if pub_time.replace(tzinfo=None) < self.cutoff_date.replace(tzinfo=None):
            return

        # Extract content
        pars = response.css('.entry-content p::text, article p::text, .elementor-widget-theme-post-content p::text').getall()
        if not pars:
            # Just default to all paragraph tags but avoid footers
            pars = response.xpath('//p[not(ancestor::footer)]//text()').getall()
            
        content = " ".join([p.strip() for p in pars if p.strip()])
        if not content:
            self.logger.warning(f"No content found for {response.url}")
            return

        author = "Addis Chamber"
        yield {
            'title': title,
            'publish_time': pub_time.replace(tzinfo=None),
            'author': author,
            'content': content,
            'url': response.url,
            'language': 'en',
            'section': 'News'
        }
