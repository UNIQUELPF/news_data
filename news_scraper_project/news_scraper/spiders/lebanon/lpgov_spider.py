import json
import logging
import re
from datetime import datetime

import psycopg2
import scrapy
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state

logger = logging.getLogger(__name__)

ARABIC_MONTHS = {
    'كانون الثاني': 1, 'شباط': 2, 'آذار': 3, 'نيسان': 4,
    'أيار': 5, 'حزيران': 6, 'تموز': 7, 'آب': 8,
    'أيلول': 9, 'تشرين الأول': 10, 'تشرين الثاني': 11, 'كانون الأول': 12
}

class LPGovSpider(scrapy.Spider):
    """
    Scrapes the Lebanese Parliament news section via its backend JSON API.
    """
    name = "lebanon_lpgov"

    country_code = 'LBN'

    country = '黎巴嫩'
    allowed_domains = ["lp.gov.lb"]
    target_table = "lebanon_lpgov_news"
    
    custom_settings = {
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 5,
        # The site has some SSL verification issues sometimes, so we ignore it:
        'DOWNLOADER_CLIENT_TLS_METHOD': "TLSv1.2",
    }

    def __init__(self, start_date=None, full_scan=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Determine cutoff date
        if start_date:
            from dateutil import parser
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

    def parse_arabic_date(self, d_str):
        if not d_str:
            return None
        
        # Non-breaking space cleaner
        d_str = d_str.replace('\xa0', ' ')
        
        m = None
        for ar_m, num_m in ARABIC_MONTHS.items():
            if ar_m in d_str:
                m = num_m
                break
                
        nums = re.findall(r'\d+', d_str)
        if m and len(nums) >= 2:
            try:
                # The typical format is "الجمعة 06  شباط 2026"
                # So nums[0] is day, nums[-1] is year
                return datetime(int(nums[-1]), m, int(nums[0]))
            except ValueError:
                pass
        return None

    def start_requests(self):
        yield scrapy.FormRequest(
            url="https://www.lp.gov.lb/Webservice.asmx/GetNews",
            formdata={"pageNumber": "1"},
            callback=self.parse_api_list,
            cb_kwargs={"page_num": 1},
            meta={'dont_verify_ssl': True}
        )

    def parse_api_list(self, response, page_num):
        try:
            items = json.loads(response.text)
        except Exception as e:
            logger.error(f"Failed to parse JSON on page {page_num}: {e}")
            return
            
        if not items:
            logger.info(f"Page {page_num} returned empty JSON. Stopping pagination.")
            return
            
        valid_items_found = False
        
        for record in items:
            # 1. Parse Date
            date_str = record.get('PublishDate') or record.get('CreationDate')
            pub_time = self.parse_arabic_date(date_str)
            
            if not pub_time:
                # Fallback to now if no date provided at all, unlikely for this CMS unless extremely old
                logger.warning(f"Could not parse date {date_str} for ID {record.get('Id')}. Falling back to now.")
                pub_time = datetime.now()
                
            if pub_time < self.cutoff_date:
                continue
                
            valid_items_found = True
            
            detail_url = f"https://www.lp.gov.lb/ContentRecordDetails?Id={record.get('Id')}"
            
            # The content might be in Summary or Description
            raw_html = record.get('Description') or record.get('Summary') or ""
            soup = BeautifulSoup(raw_html, "html.parser")
            content = soup.get_text(separator=" ", strip=True)
            
            # If Description is missing or terribly short, we fetch the details page
            if len(content) < 50 and record.get('Id'):
                yield scrapy.Request(
                    url=detail_url,
                    callback=self.parse_detail,
                    cb_kwargs={"pub_time": pub_time, "title": record.get('Title')},
                    meta={'dont_verify_ssl': True}
                )
            else:
                news_item = NewsItem()
                news_item['url'] = detail_url
                news_item['title'] = record.get('Title', 'No Title').strip()
                news_item['content'] = content
                news_item['publish_time'] = pub_time.strftime("%Y-%m-%d %H:%M:%S")
                news_item['author'] = "LP.gov"
                news_item['language'] = "ar"
                news_item['section'] = record.get('CategoryName') or "News"
                yield news_item
                
        # Handle Pagination
        if valid_items_found:
            next_page = page_num + 1
            yield scrapy.FormRequest(
                url="https://www.lp.gov.lb/Webservice.asmx/GetNews",
                formdata={"pageNumber": str(next_page)},
                callback=self.parse_api_list,
                cb_kwargs={"page_num": next_page},
                meta={'dont_verify_ssl': True}
            )
        else:
            logger.info(f"Reached cutoff date or invalid items on page {page_num}. Stopping.")

    def parse_detail(self, response, pub_time, title):
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find the content block
        content_div = soup.select_one('#Content') or soup.select_one('.the_content') or soup.select_one('.entry-content')
        if content_div:
            content = content_div.get_text(separator=" ", strip=True)
        else:
            content = "No content"
            
        real_title = soup.select_one('.entry-title')
        if real_title:
            title = real_title.get_text(strip=True)
            
        news_item = NewsItem()
        news_item['url'] = response.url
        news_item['title'] = title
        news_item['content'] = content
        news_item['publish_time'] = pub_time.strftime("%Y-%m-%d %H:%M:%S")
        news_item['author'] = "LP.gov"
        news_item['language'] = "ar"
        news_item['section'] = "News"
        yield news_item
