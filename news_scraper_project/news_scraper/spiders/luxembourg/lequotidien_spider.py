import logging
from datetime import datetime

import psycopg2
import scrapy
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state

logger = logging.getLogger(__name__)

class LeQuotidienSpider(scrapy.Spider):
    """
    Scrapes the Le Quotidien (lequotidien.lu) news site.
    Uses standard WP-like server-side rendering pagination.
    """
    name = "luxembourg_lequotidien"

    country_code = 'LUX'

    country = '卢森堡'
    allowed_domains = ["lequotidien.lu"]
    target_table = "luxembourg_lequotidien_news"
    
    custom_settings = {
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        # Standard generic user agent to avoid basic blocks
        'USER_AGENT': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }

    start_categories = [
        'a-la-une', 'luxembourg', 'politique-societe', 'economie', 
        'monde', 'grande-region', 'police-justice', 'sport-national', 
        'culture', 'lifestyle'
    ]

    def __init__(self, start_date=None, full_scan=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Determine cutoff date
        if start_date:
            self.cutoff_date = date_parser.parse(start_date).replace(tzinfo=None)
            logger.info(f"Using explicitly provided start_date: {self.cutoff_date}")
        elif full_scan:
            self.cutoff_date = datetime(2026, 1, 1)
            logger.info("Doing a FULL SCAN back to 2026-01-01.")
        else:
            self.cutoff_date = self.get_latest_db_date()
            logger.info(f"Using latest DB publish_time as cutoff: {self.cutoff_date}")
            
        self.init_db()

    def get_latest_db_date(self):
        try:
            conn = psycopg2.connect(**POSTGRES_SETTINGS)
            cur = conn.cursor()
            cur.execute(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = '{self.target_table}'
                )
            """)
            if not cur.fetchone()[0]:
                return datetime(2026, 1, 1)

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
            logger.warning(f"Failed to get max date from DB, defaulting to 2026-01-01: {e}")
            
        return datetime(2026, 1, 1)

    def init_db(self):
        try:
            conn = psycopg2.connect(**POSTGRES_SETTINGS)
            cur = conn.cursor()
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.target_table} (
                    url TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT,
                    publish_time TIMESTAMP NOT NULL,
                    author VARCHAR(255),
                    language VARCHAR(50),
                    section VARCHAR(100),
                    scraped_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize table {self.target_table}: {e}")

    def start_requests(self):
        for cat in self.start_categories:
            url = f"https://lequotidien.lu/{cat}/page/1/"
            yield scrapy.Request(
                url=url,
                callback=self.parse_list,
                cb_kwargs={"cat": cat, "page": 1}
            )

    def parse_list(self, response, cat, page):
        soup = BeautifulSoup(response.text, "html.parser")
        
        main_container = soup.select_one('#main-content') or soup.select_one('main') or soup.find(id='content') or soup
        articles = main_container.find_all('article')
        
        if not articles:
            logger.info(f"No articles found on {cat} page {page}. Stopping.")
            return
            
        valid_items_found = False
        
        for p in articles:
            a_tag = p.find('a')
            if not a_tag or not a_tag.get('href'):
                continue
                
            href = a_tag.get('href')
            detail_url = href if href.startswith('http') else f"https://lequotidien.lu{href}"
            
            # Extract basic info
            date_el = p.select_one('.tie-date') or p.select_one('time') or p.select_one('.date')
            date_text = date_el.text.strip() if date_el else ""
            
            title_el = p.find(['h2', 'h3'])
            title = title_el.text.strip() if title_el else ""
            
            if not date_text or not title:
                continue
                
            try:
                # Typically format DD/MM/YYYY
                pub_time = datetime.strptime(date_text, "%d/%m/%Y")
            except Exception:
                try:
                    # Fallback parser
                    pub_time = date_parser.parse(date_text).replace(tzinfo=None)
                except Exception:
                    continue  # skip invalid
                    
            if pub_time < self.cutoff_date:
                continue
                
            valid_items_found = True
            
            yield scrapy.Request(
                url=detail_url,
                callback=self.parse_detail,
                cb_kwargs={
                    "pub_time": pub_time,
                    "title": title,
                    "section": cat
                }
            )
            
        # Pagination handling
        if valid_items_found:
            next_page = page + 1
            next_url = f"https://lequotidien.lu/{cat}/page/{next_page}/"
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_list,
                cb_kwargs={"cat": cat, "page": next_page}
            )
        else:
            logger.info(f"Reached cutoff for {cat} at page {page}. Stopping.")

    def parse_detail(self, response, pub_time, title, section):
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Primary container
        content_node = soup.select_one('.entry-content') or soup.select_one('article')
        
        if not content_node:
            content_node = soup.select_one('#post-content') or soup.find('body')
            
        # Optional: cleanup typical clutter like embedded ads or 'Read Also'
        for unwanted in content_node.select('.related-posts, .yarpp-related, .advertisement, script, style'):
            unwanted.decompose()
            
        content = content_node.get_text(separator="\n", strip=True)
        
        # Look for author
        author = "Le Quotidien"
        author_el = soup.select_one('.author-name') or soup.select_one('.post-meta-author')
        if author_el:
            author = author_el.get_text(separator=" ", strip=True)
            
        news_item = NewsItem()
        news_item['url'] = response.url
        news_item['title'] = title
        news_item['content'] = content
        news_item['publish_time'] = pub_time.strftime("%Y-%m-%d %H:%M:%S")
        news_item['author'] = author
        news_item['language'] = "fr"
        news_item['section'] = section
        yield news_item
