import scrapy
import json
import psycopg2
from datetime import datetime
import re
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.items import NewsItem
from bs4 import BeautifulSoup

class MalayMailSpider(scrapy.Spider):
    name = "malaysia_malaymail"
    allowed_domains = ["malaymail.com"]
    target_table = "malaysia_malaymail_news"
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS': 8,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }

    # Money section
    BASE_URL = "https://www.malaymail.com/morearticles/money?page={page}"

    def __init__(self, start_date=None, *args, **kwargs):
        super(MalayMailSpider, self).__init__(*args, **kwargs)
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

    def start_requests(self):
        yield scrapy.Request(self.BASE_URL.format(page=1), callback=self.parse_list, meta={'page': 1})

    def parse_list(self, response):
        page = response.meta['page']
        
        # Malay Mail morearticles page contains a list of articles under div.article-item or similar
        items = response.css('div.article-item')
        if not items:
            # Fallback to broader selector if structure changed
            items = response.xpath("//h2/parent::div")
        
        if not items:
            self.logger.info(f"No more items on page {page}")
            return

        self.logger.info(f"Page {page}: found {len(items)} items")
            
        for item in items:
            url = item.css('h2 a ::attr(href)').get()
            if not url: continue
            if not url.startswith('http'):
                url = response.urljoin(url)
            
            # Malay Mail URLs typically contain the date: /news/money/YYYY/MM/DD/...
            # Example: /news/money/2026/03/25/...
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
            if date_match:
                year, month, day = date_match.groups()
                url_date = datetime(int(year), int(month), int(day))
                if url_date < self.cutoff_date:
                    self.logger.info(f"Reached date cutoff {self.cutoff_date} at {url}")
                    # Since it is sorted by newest, we can potentially stop or skip.
                    # We continue to skip all items, but this might hit the page limit soon.
                    continue

            yield scrapy.Request(url, callback=self.parse_article)
            
        # Pagination
        if len(items) > 0:
            next_page = page + 1
            if next_page <= 1000: # Safety cap
                yield scrapy.Request(self.BASE_URL.format(page=next_page), callback=self.parse_list, meta={'page': next_page})

    def parse_article(self, response):
        # Extract metadata
        title = response.css('h1 ::text').get()
        if not title:
            # Fallback
            title = response.css('meta[property="og:title"]::attr(content)').get()

        # Date extraction from meta
        publish_time_str = response.css('meta[property="article:published_time"]::attr(content)').get()
        if not publish_time_str:
            # Fallback to URL date but try to find it in page text
            # Often found in <span class="article-date">
            pass
            
        try:
            # 2026-03-25 13:49:47
            dt = datetime.strptime(publish_time_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            # Fallback for ISO format
            try:
                dt = datetime.fromisoformat(publish_time_str.replace('Z', '+00:00')).replace(tzinfo=None)
            except:
                self.logger.error(f"Failed to parse time {publish_time_str} for {response.url}")
                return

        if dt < self.cutoff_date:
            return

        # Content
        # div.article-body
        body_html = response.css('div.article-body').get() or response.css('div.item-content').get()
            
        if body_html:
            soup = BeautifulSoup(body_html, 'html.parser')
            # Clean up unwanted elements
            # Decompose ads, scripts, related story widgets
            for s in soup(['script', 'style', 'iframe', 'ins', 'div.related-articles', 'div.read-more-box']):
                s.decompose()
            content_text = soup.get_text("\n\n").strip()
        else:
            # Fallback extraction from paragraphs
            paragraphs = response.css('p ::text').getall()
            content_text = "\n\n".join([p.strip() for p in paragraphs if p.strip()]).strip()


        # Author
        # meta[name="author"] or meta[property="article:author"]
        author = response.css('meta[property="article:author"]::attr(content)').get()
        if not author:
            # Try to find it in <a> under some class
            author = response.css('a[rel="author"] ::text').get() or "Malay Mail"

        item = NewsItem()
        item['title'] = (title or "Untitled").strip()
        item['url'] = response.url
        item['publish_time'] = dt.strftime("%Y-%m-%d %H:%M:%S")
        item['author'] = str(author).strip()
        item['content'] = content_text
        item['section'] = "Money"
        item['language'] = "en"
        
        yield item
