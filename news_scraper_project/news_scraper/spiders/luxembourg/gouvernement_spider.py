import html
import json
import re
from datetime import datetime

import psycopg2
import scrapy
from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state


class GouvernementSpider(scrapy.Spider):
    name = "luxembourg_gouvernement"

    country_code = 'LUX'

    country = '卢森堡'
    allowed_domains = ["gouvernement.lu"]
    target_table = "luxembourg_gouvernement_news"
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.5,
    }

    def __init__(self, start_date=None, *args, **kwargs):
        super(GouvernementSpider, self).__init__(*args, **kwargs)
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
        # Start with page 1
        url = "https://gouvernement.lu/content/gouvernement2024/fr/actualites/toutes_actualites/jcr:content/root/root-responsivegrid/content-responsivegrid/sections-responsivegrid/section/col1/search.searchresults-content.html?format=json&page=1"
        yield scrapy.Request(url, callback=self.parse_list, meta={'page': 1})

    def parse_list(self, response):
        page = response.meta['page']
        
        # The response is HTML containing a div with data-json attribute
        match = re.search(r'data-json=\"(.*?)\"', response.text, re.DOTALL)
        if not match:
            self.logger.error(f"Failed to find data-json on {response.url}")
            return
            
        try:
            encoded_json = match.group(1)
            decoded_json = html.unescape(encoded_json)
            data = json.loads(decoded_json)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
            return
            
        items = data.get('search', {}).get('items', [])
        if not items:
            self.logger.info(f"No items found on page {page}")
            return
            
        self.logger.info(f"Page {page}: found {len(items)} items")
            
        oldest_on_page = None
        
        for item in items:
            page_data = item.get('page', {})
            title = page_data.get('title')
            url_rel = item.get('url') # e.g. //gouvernement.lu/fr/actualites/toutes_actualites/communiques/2026/03-mars/24-deprez-spautz-healthcareers.html
            
            # publish_time logic
            # Field: hitMetaData.first_release_date_hour -> "2026/03/24 18:00:10"
            metadata = item.get('hitMetaData', {})
            pub_date_str = metadata.get('first_release_date_hour') or item.get('first_release_date_hour')
            
            if not pub_date_str:
                # Fallback to startDateFormating
                pub_date_str = item.get('startDateFormating', {}).get('fulltimeString')
                
            if not pub_date_str:
                self.logger.warning(f"Item missing publish date: {title}")
                continue
                
            try:
                # Format: YYYY/MM/DD HH:MM:SS
                dt = datetime.strptime(pub_date_str, "%Y/%m/%d %H:%M:%S")
            except Exception as e:
                self.logger.warning(f"Failed to parse date {pub_date_str}: {e}")
                continue
                
            # self.logger.debug(f"Item: {title}, Date: {dt}")

            if oldest_on_page is None or dt < oldest_on_page:
                oldest_on_page = dt
                
            if dt >= self.cutoff_date:
                full_url = url_rel
                if full_url.startswith('//'):
                    full_url = 'https:' + full_url
                elif full_url.startswith('/'):
                    full_url = 'https://gouvernement.lu' + full_url
                
                yield scrapy.Request(
                    full_url, 
                    callback=self.parse_article,
                    meta={
                        'title': title,
                        'publish_time': dt,
                        'section': item.get('third_level', 'news')
                    }
                )
        
        # Pagination
        if oldest_on_page and oldest_on_page >= self.cutoff_date:
            next_page = page + 1
            next_url = f"https://gouvernement.lu/content/gouvernement2024/fr/actualites/toutes_actualites/jcr:content/root/root-responsivegrid/content-responsivegrid/sections-responsivegrid/section/col1/search.searchresults-content.html?format=json&page={next_page}"
            yield scrapy.Request(next_url, callback=self.parse_list, meta={'page': next_page})
        else:
            self.logger.info(f"Reached cutoff or end of content at page {page}")

    def parse_article(self, response):
        title = response.meta['title']
        publish_time = response.meta['publish_time']
        section = response.meta['section']
        
        # Extract content from div.cmp-text
        # We should join all of them, but sometimes there are footer/header texts.
        # But for Gouvernement.lu, it seems fairly clean.
        content_blocks = response.css('div.cmp-text').xpath('.//p | .//h2 | .//h3 | .//h4 | .//li')
        paragraphs = []
        for block in content_blocks:
            text = block.xpath('string(.)').get()
            if text:
                text = text.strip()
                if text and text not in paragraphs:
                    paragraphs.append(text)
        
        content_text = "\n\n".join(paragraphs)
        
        # Sometimes there's a more specific content area. Let's try to refine if possible.
        # Looking at the curl output, 'cmp-text' is used for the main body parts.
        
        if not content_text:
            # Fallback if cmp-text is not enough
            content_text = "\n\n".join([p.strip() for p in response.css('div.cmp-text p::text').getall() if p.strip()])

        if not content_text:
            self.logger.warning(f"No content extracted for {response.url}")
            return

        item = NewsItem()
        item['title'] = title
        item['url'] = response.url
        item['publish_time'] = publish_time.strftime("%Y-%m-%d %H:%M:%S")
        item['author'] = "" # Usually not specified per-article in government press releases
        item['content'] = content_text
        item['section'] = section
        item['language'] = "fr"
        
        yield item
