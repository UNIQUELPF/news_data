# 哈萨克斯坦kapital spider爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.items import KapitalItem
from datetime import datetime, timezone
import json
from bs4 import BeautifulSoup
import re
from news_scraper.utils import get_dynamic_cutoff

class KapitalSpider(scrapy.Spider):
    name = 'kapital'

    country_code = 'KAZ'

    country = '哈萨克斯坦'
    allowed_domains = ['kapital.kz']
    
    custom_settings = {
        'CONCURRENT_REQUESTS': 5,
        'DOWNLOAD_DELAY': 0.5,
        'PLAYWRIGHT_MAX_PAGES_PER_CONTEXT': 5,
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000
    }
    
    # Categories to crawl
    CATEGORIES = [
        {'name': 'economic', 'path': 'economic'},
        {'name': 'finance', 'path': 'finance'},
        {'name': 'investments', 'path': 'project/investments'},
        {'name': 'business', 'path': 'business'},
        {'name': 'technology', 'path': 'tehnology'}
    ]
    
    BUILD_ID = 'R-RoxUoENsdYwDpD0DB9c' # Fallback build ID
    CUTOFF_DATE = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(KapitalSpider, cls).from_crawler(crawler, *args, **kwargs)
        base_cutoff = get_dynamic_cutoff(crawler.settings, 'news_kapital', spider_name=spider.name)
        spider.CUTOFF_DATE = base_cutoff.replace(tzinfo=timezone.utc)
        return spider

    def start_requests(self):
        # First visit homepage to get fresh buildId
        yield scrapy.Request(
            'https://kapital.kz/',
            callback=self.parse_homepage,
            meta={'playwright': True, 'playwright_include_page': False}
        )

    def parse_homepage(self, response):
        # Extract buildId from __NEXT_DATA__
        soup = BeautifulSoup(response.text, 'html.parser')
        next_data_script = soup.find('script', id='__NEXT_DATA__')
        if next_data_script:
            try:
                data = json.loads(next_data_script.string)
                self.BUILD_ID = data.get('buildId', self.BUILD_ID)
                self.logger.info(f"Dynamic Build ID found: {self.BUILD_ID}")
            except Exception as e:
                self.logger.warning(f"Failed to parse __NEXT_DATA__: {e}")

        # Start crawling each category
        for cat in self.CATEGORIES:
            yield self.make_json_request(cat['name'], cat['path'], 1)

    def make_json_request(self, cat_name, cat_path, page):
        # Pattern: /_next/data/{buildId}/ru/{path}.json?page={page}&category={name}
        # Note: investments path is 'project/investments'
        base_cat = cat_path.split('/')[-1]
        url = f"https://kapital.kz/_next/data/{self.BUILD_ID}/ru/{cat_path}.json?page={page}&category={base_cat}"
        return scrapy.Request(
            url,
            callback=self.parse_json_list,
            meta={'cat_name': cat_name, 'cat_path': cat_path, 'page': page}
        )

    def parse_json_list(self, response):
        try:
            data = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
            return

        cat_name = response.meta['cat_name']
        cat_path = response.meta['cat_path']
        page = response.meta['page']
        
        # Determine the path to articles
        # Usually: pageProps -> dehydratedState -> queries -> state -> data -> articles OR rows
        queries = data.get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
        
        main_articles = []
        sidebar_articles = []
        
        # 1. Main articles (from the 'articles' query) - these determine pagination
        for q in queries:
            q_key = q.get('queryKey', [])
            if q_key and q_key[0] == 'articles':
                q_data = q.get('state', {}).get('data', {})
                if isinstance(q_data, dict):
                    rows = q_data.get('rows') or q_data.get('articles')
                    if rows:
                        main_articles.extend(rows)
        
        # 2. Sidebar/Extras articles (from 'widgets_sidebar' and others)
        # These are scraped but don't affect pagination
        for q in queries:
            q_key = q.get('queryKey', [])
            if q_key and q_key[0] in ['widgets_sidebar', 'longread', 'important']:
                q_data = q.get('state', {}).get('data', {})
                if isinstance(q_data, dict):
                    # Loop through all values in the data object to find arrays
                    for val in q_data.values():
                        if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict) and (val[0].get('title') or val[0].get('slug')):
                            sidebar_articles.extend(val)
        
        # Combine both lists for processing
        all_articles = main_articles + sidebar_articles
        
        if not all_articles:
            self.logger.info(f"No articles found for {cat_name} on page {page}")
            return

        # Deduplicate within this page (in case some items are in both list and sidebar)
        seen_ids = set()
        unique_articles = []
        for art in all_articles:
            art_id = art.get('id')
            if art_id not in seen_ids:
                seen_ids.add(art_id)
                unique_articles.append(art)
        
        articles = unique_articles
        main_article_ids = {art.get('id') for art in main_articles}
        self.logger.info(f"Page {page} for {cat_name}: Found {len(articles)} unique articles ({len(main_articles)} main + sidebar).")

        reached_cutoff = False
        for art in articles:
            # Fields: title, slug, published_at (ISO), id
            published_str = art.get('published_at') or art.get('published')
            # Skip if no date or if date is not a string (e.g., boolean True)
            if not published_str or not isinstance(published_str, str):
                continue
            
            # published_at: 2026-01-28T06:43:04.000Z
            try:
                # Basic parsing, dateutil might be better but let's try standard
                publish_time = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
            except Exception:
                # Fallback for other formats
                try:
                    publish_time = datetime.strptime(published_str[:19], '%Y-%m-%dT%H:%M:%S')
                    # Make this fallback datetime timezone-aware immediately
                    publish_time = publish_time.replace(tzinfo=timezone.utc)
                except Exception:
                    self.logger.warning(f"Failed to parse date: {published_str}")
                    continue

            # Ensure timezone-awareness for all parsed datetimes
            if publish_time.tzinfo is None:
                # Make naive datetime aware by adding UTC (standard for this site)
                publish_time = publish_time.replace(tzinfo=timezone.utc)
            else:
                # Convert to UTC for consistent comparison
                publish_time = publish_time.astimezone(timezone.utc)

            # Check if article is before cutoff
            if publish_time < self.CUTOFF_DATE:
                # Only mark cutoff if this is a MAIN article (not sidebar)
                # Sidebar articles can be old but shouldn't stop pagination
                if art.get('id') in main_article_ids:
                    reached_cutoff = True
                continue  # Skip this article but continue processing others
            
            # Construct detail URL
            # https://kapital.kz/{category}/{id}/{slug}.html
            # Note: art['category']['slug'] might be more accurate than cat_name
            cat_slug = art.get('category', {}).get('slug') or cat_name
            article_id = art.get('id')
            slug = art.get('slug')
            if article_id and slug:
                detail_url = f"https://kapital.kz/{cat_slug}/{article_id}/{slug}.html"
                yield scrapy.Request(
                    detail_url,
                    callback=self.parse_detail,
                    meta={
                        'item_data': {
                            'category': cat_name,
                            'title': art.get('title'),
                            'url': detail_url,
                            'publish_time': publish_time
                        },
                        'playwright': True,
                        'playwright_include_page': False,
                        'playwright_page_goto_kwargs': {
                            'wait_until': 'domcontentloaded',
                            'timeout': 60000
                        }
                    }
                )

        # Only stop pagination if we found main articles before cutoff
        if reached_cutoff:
            self.logger.info(f"Reached cutoff for {cat_name} on page {page}, stopping pagination")
        
        if not reached_cutoff and page < 100: # Limit safe depth
            yield self.make_json_request(cat_name, cat_path, page + 1)



    def parse_detail(self, response):
        item_data = response.meta['item_data']
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Standard article tag found during research
        article_tag = soup.find('article') or soup.find('div', class_=re.compile(r'article__body|content-body'))
        if not article_tag:
            # Fallback to general content container
            self.logger.warning(f"No <article> or body tag found for {response.url}. Attempting generic extraction.")
            article_tag = soup.find('main') or soup
            
        # Cleaning logic
        for s in article_tag.select('script, style, .social-share, .tags, [id*="adfox"], .adfox, .article__tags, .banner, .adv'):
            s.decompose()
            
        # Extract content
        # Collect all paragraphs and headers from the container
        content_parts = []
        for el in article_tag.find_all(['p', 'h2', 'h3', 'h4']):
            # Filter out very short texts or UI elements
            txt = el.get_text(strip=True)
            if txt and len(txt) > 10:
                # Avoid duplicates caused by nested tags if any
                if not any(txt in p for p in content_parts):
                    content_parts.append(txt)
                
        full_text = "\n\n".join(content_parts)
        
        if not full_text:
            self.logger.warning(f"Extracted content is empty for {response.url}")
            return
        
        item = KapitalItem()
        item['type'] = 'kapital'
        item['category'] = item_data['category']
        item['title'] = item_data['title']
        item['url'] = item_data['url']
        item['publish_time'] = item_data['publish_time']
        item['content'] = full_text
        item['crawl_time'] = datetime.now()
        
        yield item
