import scrapy
import json
import psycopg2
from datetime import datetime, timedelta
import re
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.items import NewsItem
from bs4 import BeautifulSoup

class SinchewSpider(scrapy.Spider):
    name = "malaysia_sinchew"
    allowed_domains = ["sinchew.com.my"]
    target_table = "malaysia_sinchew_news"
    
    # AJAX API endpoint for category posts
    # cat=3 for Finance (财经)
    API_URL = "https://www.sinchew.com.my/ajx-api/category_posts/?cat=3&page={page}&nooffset=false&editorialcat=0&posts_per_pages=10"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS': 8,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
        }
    }

    def __init__(self, start_date=None, *args, **kwargs):
        super(SinchewSpider, self).__init__(*args, **kwargs)
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
        url = self.API_URL.format(page=1)
        yield scrapy.Request(url, callback=self.parse_list, meta={'page': 1})

    def parse_list(self, response):
        page = response.meta['page']
        try:
            items = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from page {page}: {e}")
            return
            
        if not items or not isinstance(items, list):
            self.logger.info(f"No more items or invalid JSON on page {page}")
            return

        self.logger.info(f"Page {page}: found {len(items)} items")
            
        for item in items:
            url = item.get('permalink')
            title = item.get('title')
            # The API returns relative or absolute URLs. We ensure it's absolute.
            if not url:
                continue
            
            # Since the API doesn't provide an absolute timestamp (only relative time_display like "18小时前"),
            # we must visit each article to check the actual date.
            yield scrapy.Request(
                url, 
                callback=self.parse_article,
                meta={'title': title}
            )
            
        # Pagination: Continue to the next page
        # Note: We don't check article date cutoff here because we only know the date after parsing the article.
        # However, if we've processed a reasonable number of pages and keep getting items, let's continue.
        # The spider will naturally stop yielding items from parse_article when cutoff is reached.
        # For full sweep, we can keep going as long as the page has 10 items.
        if len(items) >= 10:
            next_page = page + 1
            if next_page <= 2000: # Safety cap
                next_url = self.API_URL.format(page=next_page)
                yield scrapy.Request(next_url, callback=self.parse_list, meta={'page': next_page})

    def parse_article(self, response):
        # We use meta tags for robust extraction
        publish_time_str = response.css('meta[property="article:published_time"]::attr(content)').get()
        if not publish_time_str:
            try:
                ld_json = response.xpath('//script[@type="application/ld+json"]/text()').get()
                if ld_json:
                    data = json.loads(ld_json)
                    if isinstance(data, list):
                        for entry in data:
                            if entry.get('@type') == 'NewsArticle':
                                publish_time_str = entry.get('datePublished')
                                break
                    else:
                        publish_time_str = data.get('datePublished')
            except:
                pass

        if not publish_time_str:
            time_text = response.css('span.time ::text').get()
            if time_text and '发布:' in time_text:
                match = re.search(r'(\d+:\d+[ap]m)\s+(\d+/\d+/\d+)', time_text)
                if match:
                    t_str = f"{match.group(2)} {match.group(1)}"
                    try:
                        dt = datetime.strptime(t_str, "%d/%m/%Y %I:%M%p")
                        publish_time_str = dt.isoformat()
                    except:
                        pass

        if not publish_time_str:
            self.logger.warning(f"Could not extract publish time for {response.url}")
            return

        try:
            if '+' in publish_time_str:
                dt = datetime.fromisoformat(publish_time_str).replace(tzinfo=None)
            else:
                dt = datetime.fromisoformat(publish_time_str)
        except Exception as e:
            self.logger.error(f"Failed to parse date {publish_time_str}: {e}")
            return

        # Date Check
        if dt < self.cutoff_date:
            self.logger.info(f"Reached date cutoff {self.cutoff_date} at {response.url} (date: {dt})")
            return

        # Title
        title = response.css('meta[property="og:title"]::attr(content)').get() or \
                response.css('h1.skip-default-style ::text').get() or \
                response.meta.get('title') or \
                response.css('title ::text').get()
        
        if title:
            title = title.split(' - ')[0].strip()

        # Content
        content_div = response.css('div.article-page-content[itemprop="articleBody"]')
        if content_div:
            soup = BeautifulSoup(content_div.get(), 'html.parser')
            for s in soup(['script', 'style', 'iframe', 'ins']):
                s.decompose()
            for ads in soup.find_all(class_='ads-frame'):
                ads.decompose()
            content_text = soup.get_text("\n\n").strip()
        else:
            paragraphs = response.css('div.article-page-content p ::text').getall()
            content_text = "\n\n".join([p.strip() for p in paragraphs if p.strip()])

        # Author
        author = response.css('meta[name="author"]::attr(content)').get() or "星洲网"

        item = NewsItem()
        item['title'] = title
        item['url'] = response.url
        item['publish_time'] = dt.strftime("%Y-%m-%d %H:%M:%S")
        item['author'] = author.strip()
        item['content'] = content_text
        item['section'] = "Finance"
        item['language'] = "zh"
        
        yield item
