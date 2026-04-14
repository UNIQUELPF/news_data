# 埃塞俄比亚ebc爬虫，负责抓取对应站点、机构或栏目内容。

import re
from datetime import datetime

import dateparser
import psycopg2
import scrapy
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state


class EthiopiaEBCSpider(scrapy.Spider):
    name = "ethiopia_ebc"

    country_code = 'ETH'

    country = '埃塞俄比亚'
    allowed_domains = ["ebc.et"]
    target_table = "ethi_ebc"
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
    }

    def __init__(self, *args, **kwargs):
        super(EthiopiaEBCSpider, self).__init__(*args, **kwargs)
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
            self.logger.error(f"Database init error: {e}")
            return datetime(2026, 1, 1)

    def start_requests(self):
        base_cat_url = "https://www.ebc.et/Home/CategorialNews?CatId=3"
        yield scrapy.Request(
            url=base_cat_url,
            callback=self.parse_list,
            meta={'page': 1, 'base_url': base_cat_url}
        )

    def parse_list(self, response):
        page = response.meta['page']
        base_cat_url = response.meta['base_url']
        
        has_older_articles = False
        new_items_found = 0
        
        # In EBC list, links are like <a href="/Home/NewsDetails?NewsId=...">
        # They are usually contained inside some div. We will extract all unique hrefs and try to guess their date
        links = response.css('a[href*="NewsDetails?NewsId="]')
        
        # We group by href
        for link in links:
            url_fragment = link.attrib.get('href')
            if not url_fragment:
                continue
                
            full_url = response.urljoin(url_fragment)
            
            if full_url in self.scraped_urls:
                continue
                
            # Find the closest parent block to scrape date text from
            parent_block = link.xpath('ancestor::div[contains(@class, "type-post") or contains(@class, "post") or contains(@class, "card") or contains(@class, "row") or contains(@class, "item")]')[0] if link.xpath('ancestor::div[contains(@class, "type-post") or contains(@class, "post") or contains(@class, "card") or contains(@class, "row") or contains(@class, "item")]') else None
            
            date_str = None
            if parent_block:
                text_content = parent_block.xpath('.//text()').getall()
                for txt in text_content:
                    txt = txt.strip()
                    # Example: Mar 18, 2026 or 18 Mar 2026
                    if re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, 20\d\d', txt):
                        date_str = txt
                        break
            
            pub_time = None
            if date_str:
                parsed = dateparser.parse(date_str, settings={'TIMEZONE': 'UTC'})
                if parsed:
                    pub_time = parsed
                    
            if pub_time and pub_time.replace(tzinfo=None) < self.cutoff_date.replace(tzinfo=None):
                self.logger.debug(f"Article {full_url} older than cutoff {self.cutoff_date}")
                self.scraped_urls.add(full_url)
                has_older_articles = True
                continue
                
            self.scraped_urls.add(full_url)
            new_items_found += 1
            
            title_text = " ".join([txt.strip() for txt in link.xpath('.//text()').getall() if txt.strip()])
            
            yield scrapy.Request(
                url=full_url,
                callback=self.parse_article,
                meta={'pub_time': pub_time, 'title': title_text}
            )
            
        # Check if there's a next page link
        next_page = response.css(f'a.page-link[href*="page={page+1}"]::attr(href)').get()
        if not next_page:
           next_page = f"/Home/CategorialNews?CatId=3&page={page+1}"

        if not has_older_articles and new_items_found > 0:
            next_url = response.urljoin(next_page)
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_list,
                meta={'page': page + 1, 'base_url': base_cat_url}
            )
        else:
            self.logger.info("Cutoff reached or no new items found. Stop pagination.")

    def parse_article(self, response):
        title = response.meta.get('title')
        if not title:
            title_elems = response.css('.post-title::text, h1.post-title::text').getall()
            title = " ".join([t.strip() for t in title_elems if t.strip()])
            if not title:
                title = response.css('h1::text').get()
        if not title:
            return
        title = title.strip()

        pub_time = response.meta.get('pub_time')
        if not pub_time:
            # Maybe the list page date extraction failed.
            # Try parsing any english date on the detail page as fallback.
            content_texts = response.xpath('//text()').getall()
            for txt in content_texts:
                if "202" in txt:
                    match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, 20\d\d', txt.strip())
                    if match:
                        parsed = dateparser.parse(match.group(), settings={'TIMEZONE': 'UTC'})
                        if parsed:
                            pub_time = parsed
                            break
            # if still no pub_time, try extracting amharic date? EBC uses ethiopian calendar so ignore and fallback to now.
            if not pub_time:
                pub_time = datetime.now()
                
        if pub_time.replace(tzinfo=None) < self.cutoff_date.replace(tzinfo=None):
            return

        pars = response.css('.post-content p::text, .article-content p::text, .description p::text').getall()
        if not pars:
            pars = response.xpath('//div[contains(@class, "post-content")]//text()').getall()
            
        content = " ".join([p.strip() for p in pars if p.strip()])
        if not content:
            return

        author = "EBC"
        author_elem = response.css('.author::text, .writer::text').get()
        if author_elem:
           author = author_elem.strip()

        yield {
            'title': title,
            'publish_time': pub_time.replace(tzinfo=None),
            'author': author,
            'content': content,
            'url': response.url,
            'language': 'am',  # the site is in Amharic
            'section': 'News'
        }
