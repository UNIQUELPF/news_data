import json
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

class WortSpider(scrapy.Spider):
    """
    Scrapes the Luxemburger Wort (wort.lu) 'neueste' news section.
    Uses Next.js internal API (api/cook/neueste/...) for pagination.
    """
    name = "luxembourg_wort"

    country_code = 'LUX'

    country = '卢森堡'
    allowed_domains = ["wort.lu"]
    target_table = "luxembourg_wort_news"
    
    custom_settings = {
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        # Site forces SSO silent login 302s if it detects a standard browser UA on API endpoints.
        'USER_AGENT': "python-requests/2.31.0",
    }

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
        self.limit = 30

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
        url = f"https://www.wort.lu/api/cook/neueste/?offset=0&count={self.limit}"
        yield scrapy.Request(
            url=url,
            callback=self.parse_api_list,
            cb_kwargs={"offset": 0},
            headers={'Accept': 'application/json'}
        )

    def parse_api_list(self, response, offset):
        try:
            resp_json = json.loads(response.text)
        except Exception as e:
            logger.error(f"Failed to parse JSON on offset {offset}: {e}")
            return
            
        data = resp_json.get('data', {})
        articles = data.get('mostRecentArticles', {}).get('items', [])
        
        if not articles:
            logger.info(f"Offset {offset} returned empty items list. Stopping.")
            return
            
        valid_items_found = False
        
        for record in articles:
            # Safely skip non-article modules and promo banners
            href = record.get('href')
            pub_date_str = record.get('published') or record.get('updated')
            
            if not href or not pub_date_str:
                continue
                
            try:
                pub_time = date_parser.parse(pub_date_str).replace(tzinfo=None)
            except Exception:
                continue
                
            if pub_time < self.cutoff_date:
                continue
                
            valid_items_found = True
            
            detail_url = f"https://www.wort.lu{href}" if href.startswith('/') else href
            
            # Additional metadata for item
            title = record.get('title') or record.get('teaserHeadline') or ""
            section_data = record.get('homeSection')
            section = section_data.get('name') if isinstance(section_data, dict) else "neueste"
            authors = ", ".join([a.get('name', '') for a in record.get('authors', []) if isinstance(a, dict) and a.get('name')])
            
            yield scrapy.Request(
                url=detail_url,
                callback=self.parse_detail,
                cb_kwargs={
                    "pub_time": pub_time,
                    "title": title,
                    "section": section,
                    "author": authors if authors else "Luxemburger Wort"
                }
            )
            
        # Pagination handling
        if valid_items_found and len(articles) == self.limit:
            next_offset = offset + self.limit
            next_url = f"https://www.wort.lu/api/cook/neueste/?offset={next_offset}&count={self.limit}"
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_api_list,
                cb_kwargs={"offset": next_offset},
                headers={'Accept': 'application/json'}
            )
        else:
            logger.info(f"Reached cutoff or end of list at offset {offset}. Stopping.")

    def parse_detail(self, response, pub_time, title, section, author):
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Primary article container, extracting standard paragraphs
        article_node = soup.select_one('article')
        content = ""
        
        if article_node:
            # Fallback to pure text extraction, stripping out noisy nav items if needed
            content = article_node.get_text(separator="\n", strip=True)
        else:
            # Failsafe
            body = soup.select_one('.article-body') or soup.find('body')
            if body:
                content = body.get_text(separator="\n", strip=True)
                
        # If the article is premium "Wort+", we still extract whatever free preview is present
        
        news_item = NewsItem()
        news_item['url'] = response.url
        news_item['title'] = title
        news_item['content'] = content
        news_item['publish_time'] = pub_time.strftime("%Y-%m-%d %H:%M:%S")
        news_item['author'] = author
        news_item['language'] = "de"
        news_item['section'] = section
        yield news_item
