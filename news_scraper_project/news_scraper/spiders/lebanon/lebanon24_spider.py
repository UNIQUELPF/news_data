import logging
from datetime import datetime

import psycopg2
import scrapy
from bs4 import BeautifulSoup
from dateutil import parser
from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state

logger = logging.getLogger(__name__)

class Lebanon24Spider(scrapy.Spider):
    name = "lebanon_lebanon24"

    country_code = 'LBN'

    country = '黎巴嫩'
    allowed_domains = ["lebanon24.com"]
    
    # Standard spider, no curl_cffi required since CF doesn't block LoadMore endpoint
    
    def __init__(self, start_date=None, full_scan=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_table = "lebanon_lebanon24_news"
        self.categories = [
            # url, category_id
            ("https://www.lebanon24.com/section/5/%D8%A5%D9%82%D8%AA%D8%B5%D8%A7%D8%AF", "5")
        ]
        
        # Determine cutoff date
        if start_date:
            self.cutoff_date = parser.parse(start_date).replace(tzinfo=None)
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

    async def start(self):
        for main_url, cat_id in self.categories:
            yield scrapy.Request(
                url=main_url,
                callback=self.parse_first_page,
                cb_kwargs={"cat_id": cat_id, "load_index": 1}
            )

    def parse_first_page(self, response, cat_id, load_index):
        # We start by scraping the first page content
        valid_count = 0
        for item in self._parse_items(response):
            valid_count += 1
            yield item
        
        # If we successfully scraped the first page, yield the first LoadMore page
        if valid_count > 0:
            next_url = f"https://www.lebanon24.com/Website/DynamicPages/LoadMore/Loadmore_DocumentCategory.aspx?loadindex={load_index}&lang=ar&ID={cat_id}"
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_list_page,
                cb_kwargs={"cat_id": cat_id, "load_index": load_index}
            )

    def parse_list_page(self, response, cat_id, load_index):
        valid_count = 0
        for item in self._parse_items(response):
            valid_count += 1
            yield item
        
        # If no valid items parsed (either hit cutoff date or no items found), we stop pagination
        if valid_count > 0:
            next_index = load_index + 1
            next_url = f"https://www.lebanon24.com/Website/DynamicPages/LoadMore/Loadmore_DocumentCategory.aspx?loadindex={next_index}&lang=ar&ID={cat_id}"
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_list_page,
                cb_kwargs={"cat_id": cat_id, "load_index": next_index}
            )
        else:
            logger.info(f"Stopping pagination for category {cat_id} at index {load_index} (hit cutoff or empty).")

    def _parse_items(self, response):
        """
        Parses article blocks from HTML soup, yields detail requests if dates are valid.
        """
        soup = BeautifulSoup(response.text, "html.parser")
        
        article_links = soup.select('a[href*="/news/"]')
        
        seen_urls = set()
        
        for a_tag in article_links:
            href = a_tag.get('href')
            if not href:
                continue
            
            url = response.urljoin(href)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            title = a_tag.text.strip()
            if not title:
                continue
            
            # Now we find the date. Typically it sits inside .CardsControls-Date
            # Traverse ancestors to find the closest wrapper containing the date
            wrapper = a_tag.find_parent('div')
            date_tag = None
            while wrapper:
                # Safeguard: if the wrapper contains too many articles, we went too far up
                if len(wrapper.select('a[href*="/news/"]')) > 5:
                    break
                date_tag = wrapper.select_one('.CardsControls-Date')
                if date_tag:
                    break
                wrapper = wrapper.find_parent('div')
                
            pub_time = None
            if date_tag:
                date_text = date_tag.text.strip()
                # format: "01:48 | 2026-03-24"
                try:
                    if "|" in date_text:
                        time_part, date_part = date_text.split('|')
                        dt_string = f"{date_part.strip()} {time_part.strip()}"
                        pub_time = parser.parse(dt_string).replace(tzinfo=None)
                    else:
                        pub_time = parser.parse(date_text).replace(tzinfo=None)
                except Exception as e:
                    logger.debug(f"Failed to parse date '{date_text}': {e}")
            
            if not pub_time:
                pub_time = datetime.now()
            
            if pub_time < self.cutoff_date:
                # We reached an article older than our cutoff. We stop counting valid items.
                continue
                
            item = NewsItem()
            item['url'] = url
            item['title'] = title
            item['content'] = "" # Content securely locked behind login page for this domain.
            item['publish_time'] = pub_time.strftime("%Y-%m-%d %H:%M:%S")
            item['author'] = "Lebanon24"
            item['language'] = "ar"
            item['section'] = "Economy"
            
            yield item
