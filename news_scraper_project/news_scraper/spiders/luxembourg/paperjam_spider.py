import scrapy
import re
import json
import psycopg2
from datetime import datetime
import dateutil.parser
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.items import NewsItem

class PaperjamSpider(scrapy.Spider):
    name = "luxembourg_paperjam"
    allowed_domains = ["paperjam.lu"]
    target_table = "luxembourg_paperjam_news"
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.5,
    }

    CATEGORIES = [
        'politique-institutions/politique',
        'politique-institutions/institutions',
        'politique-institutions/economie',
        'politique-institutions/justice',
        'politique-institutions/education',
        'politique-institutions/europe',
        'politique-institutions/monde',
        'place-financiere-marches/banques',
        'place-financiere-marches/fonds',
        'place-financiere-marches/assurances',
        'place-financiere-marches/wealth-management',
        'place-financiere-marches/private-equity',
        'place-financiere-marches/fintech',
        'place-financiere-marches/marches-financiers',
        'entreprises-strategies/finance-legal',
        'entreprises-strategies/services-conseils',
        'entreprises-strategies/technologies',
        'entreprises-strategies/industrie',
        'entreprises-strategies/immobilier',
        'entreprises-strategies/artisanat',
        'entreprises-strategies/commerce',
        'communautes-expertises/knowledge',
        'communautes-expertises/mouvements',
        'communautes-expertises/communiques-de-presse',
        'lifestyle-vie-pratique/foodzilla',
        'lifestyle-vie-pratique/foodzilla-guide',
        'lifestyle-vie-pratique/sorties',
        'lifestyle-vie-pratique/bien-etre',
        'lifestyle-vie-pratique/style',
        'lifestyle-vie-pratique/habitat',
        'lifestyle-vie-pratique/voyages',
        'lifestyle-vie-pratique/techno',
        'lifestyle-vie-pratique/drive',
        'lifestyle-vie-pratique/argent',
        'lifestyle-vie-pratique/carriere',
        'lifestyle-vie-pratique/mobilite',
        'lifestyle-vie-pratique/concours'
    ]

    def __init__(self, start_date=None, *args, **kwargs):
        super(PaperjamSpider, self).__init__(*args, **kwargs)
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

    async def start(self):
        for cat in self.CATEGORIES:
            url = f"https://paperjam.lu/sector/{cat}?page=1"
            yield scrapy.Request(url, callback=self.parse_list, meta={'cat': cat, 'page': 1})

    def find_articles(self, obj):
        found = []
        if isinstance(obj, dict):
            if 'slug' in obj and 'publicationDate' in obj:
                found.append(obj)
            for v in obj.values():
                found.extend(self.find_articles(v))
        elif isinstance(obj, list):
            for item in obj:
                found.extend(self.find_articles(item))
        return found

    def parse_list(self, response):
        cat = response.meta['cat']
        page = response.meta['page']
        
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
        if not match:
            self.logger.error(f"Failed to find __NEXT_DATA__ on {response.url}")
            return
            
        data = json.loads(match.group(1))
        sub_page = data.get('props', {}).get('pageProps', {}).get('data', {}).get('subSectorPage', {})
        articles_data = sub_page.get('articles', {})
        
        if not articles_data:
            self.logger.info(f"No articles mapped on {response.url}")
            return
            
        all_slugs = set()
        article_items = []
        
        extracted = self.find_articles(articles_data)
        for item in extracted:
            slug = item.get('slug')
            if slug and slug not in all_slugs:
                all_slugs.add(slug)
                article_items.append(item)
                    
        if not article_items:
            return
            
        oldest_date = None
        for item in article_items:
            pub_date_str = item.get('publicationDate')
            if not pub_date_str:
                continue
            
            try:
                dt = dateutil.parser.isoparse(pub_date_str).replace(tzinfo=None)
            except Exception:
                continue
                
            if oldest_date is None or dt < oldest_date:
                oldest_date = dt
                
            if dt >= self.cutoff_date:
                article_url = f"https://paperjam.lu/article/{item['slug']}"
                yield scrapy.Request(article_url, callback=self.parse_article)
                
        # Pagination handling
        if oldest_date and oldest_date >= self.cutoff_date:
            pagination = sub_page.get('pagination', {})
            count = pagination.get('count', 0)
            offset = pagination.get('offset', 0)
            limit = pagination.get('limit', 16)
            
            if offset + limit < count:
                next_page = page + 1
                next_url = f"https://paperjam.lu/sector/{cat}?page={next_page}"
                yield scrapy.Request(next_url, callback=self.parse_list, meta={'cat': cat, 'page': next_page})
            else:
                self.logger.info(f"Reached end of pagination for {cat}")
        else:
            self.logger.info(f"Reached cutoff for {cat} at page {page}")

    def extract_text(self, obj):
        text = ""
        if isinstance(obj, dict):
            if 'text' in obj and isinstance(obj['text'], str):
                text += obj['text']
            for k, v in obj.items():
                if k != 'text':
                    text += self.extract_text(v)
        elif isinstance(obj, list):
            for item in obj:
                text += self.extract_text(item)
        return text

    def parse_article(self, response):
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
        if not match:
            return
            
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return

        article = data.get('props', {}).get('pageProps', {}).get('data', {}).get('article')
        if not article:
            return
            
        metadata = article.get('metadata', {})
        title = metadata.get('title', '')
        if not title:
            return

        pub_date_str = article.get('publication', {}).get('date') or metadata.get('creationDate')
        if not pub_date_str:
            return
            
        try:
            publish_time = dateutil.parser.isoparse(pub_date_str).replace(tzinfo=None)
        except Exception:
            return
            
        author_data = metadata.get('author')
        author = author_data.get('name') if isinstance(author_data, dict) else ""
        
        top_cat = metadata.get('topCategory', {})
        cat_sector = top_cat.get('sector', '')
        cat_subsector = top_cat.get('subSector', '')
        category = f"{cat_sector}/{cat_subsector}" if cat_sector else "Unknown"
        
        content_dict = article.get('content', {})
        paragraphs = []
        
        intro = content_dict.get('introduction')
        if intro:
            intro_text = self.extract_text(intro).strip()
            if intro_text:
                paragraphs.append(intro_text)
                
        body = content_dict.get('bodyContents')
        if isinstance(body, list):
            for block in body:
                if isinstance(block, list) and len(block) == 2:
                    block_text = self.extract_text(block[1])
                    # Remove multiple spaces & line breaks inside paragraph
                    block_text = re.sub(r'\s+', ' ', block_text).strip()
                    if block_text:
                        paragraphs.append(block_text)
                        
        content_text = "\n\n".join(paragraphs)
        if not content_text:
            self.logger.warning(f"No content found for: {response.url}")
            return
            
        item = NewsItem()
        item['title'] = title
        item['url'] = response.url
        item['publish_time'] = publish_time.strftime("%Y-%m-%d %H:%M:%S")
        item['author'] = author
        item['content'] = content_text
        item['section'] = category
        item['language'] = "fr"
        
        yield item
