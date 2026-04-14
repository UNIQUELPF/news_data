# 埃塞俄比亚reporter爬虫，负责抓取对应站点、机构或栏目内容。

from datetime import datetime

import psycopg2
import scrapy
from bs4 import BeautifulSoup
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state


class EthiopiaReporterSpider(scrapy.Spider):
    name = "ethiopia_reporter"

    country_code = 'ETH'

    country = '埃塞俄比亚'
    allowed_domains = ["thereporterethiopia.com"]
    target_table = "ethi_reporter"
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors'
        }
    }

    def __init__(self, *args, **kwargs):
        super(EthiopiaReporterSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = self._init_db()
        self.logger.info(f"Spider initialized. Cutoff date set to: {self.cutoff_date}")
        self.current_page = 1
        self.base_api_url = 'https://www.thereporterethiopia.com/wp-json/wp/v2/posts?categories=1960&_embed=1&per_page=50&page={}'
        
    def _init_db(self):
        try:
            db_settings = POSTGRES_SETTINGS.copy()
            if 'database' in db_settings:
                # Correct naming if needed
                db_settings['dbname'] = db_settings.pop('database')
            elif 'db' in db_settings:
                db_settings['dbname'] = db_settings.pop('db')
                
            conn = psycopg2.connect(**db_settings)
            cur = conn.cursor()
            
            # Create table if not exists
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
            
            cur.close()
            conn.close()

            state = get_incremental_state(
                self.settings,
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=datetime(2026, 1, 1),
                full_scan=False,
            )
            return state["cutoff_date"]
        except Exception as e:
            self.logger.error(f"Database initialization error: {e}")
            return datetime(2026, 1, 1)

    def start_requests(self):
        yield scrapy.Request(
            url=self.base_api_url.format(self.current_page),
            callback=self.parse_api,
            dont_filter=True
        )

    def parse_api(self, response):
        try:
            data = response.json()
        except:
            self.logger.error(f"Failed to decode JSON on page {self.current_page}")
            return
            
        if not data or not isinstance(data, list):
            self.logger.info(f"No more articles or end of API reached at page {self.current_page}")
            return
            
        found_recent_articles = False
        
        for post in data:
            # Check date
            date_str = post.get('date') or post.get('date_gmt')
            pub_time = None
            if date_str:
                pub_time = datetime.fromisoformat(date_str)
                
            if pub_time and pub_time.replace(tzinfo=None) < self.cutoff_date.replace(tzinfo=None):
                self.logger.debug(f"Article {post.get('link')} is older than cutoff {self.cutoff_date}")
                continue
                
            found_recent_articles = True
            
            title = post.get('title', {}).get('rendered', '')
            if title:
                title = BeautifulSoup(title, "html.parser").text.strip()
                
            content_html = post.get('content', {}).get('rendered', '')
            content = ''
            if content_html:
                soup = BeautifulSoup(content_html, "html.parser")
                content = " ".join([p.text.strip() for p in soup.find_all('p') if p.text.strip()])
                
            url = post.get('link')
            
            # Author
            author = 'Reporter Staff'
            try:
                author_list = post.get('_embedded', {}).get('author', [])
                if author_list and len(author_list) > 0:
                    author = author_list[0].get('name', 'Reporter Staff')
            except:
                pass
                
            if not content or not title or not url:
                continue

            item = {
                'title': title,
                'publish_time': pub_time.replace(tzinfo=None),
                'author': author,
                'content': content,
                'url': url,
                'language': 'en',
                'section': 'latest-news-in-ethiopia'
            }
            yield item
            
        if found_recent_articles:
            self.current_page += 1
            next_url = self.base_api_url.format(self.current_page)
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_api,
                dont_filter=True
            )
        else:
            self.logger.info(f"All articles on page {self.current_page} are older than {self.cutoff_date}. Stopping pagination.")
