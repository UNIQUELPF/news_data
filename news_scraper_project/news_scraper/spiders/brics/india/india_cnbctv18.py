# 印度cnbctv18爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from scrapy.spiders import SitemapSpider
import re
from datetime import datetime
from news_scraper.utils import get_incremental_state

class IndiaCnbctv18Spider(SitemapSpider):
    name = 'india_cnbctv18'

    country_code = 'IND'

    country = '印度'
    allowed_domains = ['cnbctv18.com']
    
    # We use their daily sitemaps endpoint which has sub-sitemaps for everyday.
    sitemap_urls = ['https://www.cnbctv18.com/commonfeeds/v1/cne/sitemap-index.xml']
    
    # Custom pipeline config to direct output to the specific table
    custom_settings = {
        'ITEM_PIPELINES': {
            'news_scraper.pipelines.PostgresPipeline': 300,
        }
    }
    
    target_table = "ind_cnbctv18"

    def __init__(self, *args, **kwargs):
        super(IndiaCnbctv18Spider, self).__init__(*args, **kwargs)
        
        # We use a compiled regex catch-all and filter URLs manually in parse_detail
        self.sitemap_rules = [
            (re.compile(r'.*'), 'parse_detail')
        ]
        
        try:
            state = get_incremental_state(
                self.settings,
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=datetime(2026, 1, 1),
                full_scan=False,
            )
            self.cutoff_date = state["cutoff_date"]
            self.seen_urls = state["scraped_urls"]
            self.logger.info(f"Loaded {len(self.seen_urls)} seen URLs via {state['source']}.")
        except Exception as e:
            self.logger.error(f"Database connection error in __init__: {e}")
            self.cutoff_date = datetime(2026, 1, 1)
            self.seen_urls = set()

    def sitemap_filter(self, entries):
        """Filter out old sitemaps to optimize crawling speed"""
        for entry in entries:
            loc = entry.get('loc', '')
            
            # If it's a daily sitemap, check the date in the URL (e.g., 2026-03-15.xml)
            if 'sitemap/daily/' in loc:
                try:
                    date_str = re.search(r'(\d{4}-\d{2}-\d{2})', loc).group(1)
                    sitemap_date = datetime.strptime(date_str, "%Y-%m-%d")
                    # If the sitemap is older than cutoff (minus 1 day buffer), skip it entirely
                    if sitemap_date < self.cutoff_date.replace(hour=0, minute=0, second=0):
                        self.logger.debug(f"Skipping old sitemap: {loc}")
                        continue
                except (AttributeError, ValueError):
                    pass
            
            yield entry

    def parse(self, response):
        """Mandatory callback for SitemapSpider to process all sub-links"""
        yield from self.parse_detail(response)

    def parse_detail(self, response):
        # Skip if already in DB
        if response.url in self.seen_urls:
            return
            
        # Date extraction - CNBCTV18 stores dates in meta tags
        date_el = response.css('meta[property="article:published_time"]::attr(content), meta[property="og:published_time"]::attr(content)').get()
        pub_time = None
        if date_el:
            try:
                # "2026-01-01T05:42:43+05:30" ISO format
                date_str = date_el.strip()
                # Strip timezone offset for basic parsing
                date_str = re.sub(r'([+-]\d{2}:\d{2})$', '', date_str).replace('T', ' ').strip()
                if '.' in date_str:
                    date_str = date_str.split('.')[0]
                pub_time = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                self.logger.debug(f"Could not parse date: {date_el}")
        
        # Check against cutoff
        if pub_time and pub_time < self.cutoff_date:
            return
            
        item = {}
        item['url'] = response.url
        
        # Title
        item['title'] = response.css('h1::text, h1.article-title::text').get(default='').strip()
        if not item['title']:
            return # Drop invalid items
            
        item['publish_time'] = pub_time
        item['language'] = 'en'
        
        # Author - try JSON-LD first, then CSS fallback
        author = None
        try:
            import json
            ld_scripts = response.css('script[type="application/ld+json"]::text').getall()
            for ld_text in ld_scripts:
                ld = json.loads(ld_text)
                if isinstance(ld, dict) and 'author' in ld:
                    a = ld['author']
                    if isinstance(a, dict):
                        author = a.get('name', '')
                    elif isinstance(a, str):
                        author = a
                    if author:
                        break
        except Exception:
            pass
        if not author:
            author = response.css('.author-name a::text, .authorname::text').get(default='').strip()
        item['author'] = author if author else None
        
        # Content - CNBCTV18 uses .articleWrap (no <p> tags inside)
        content_parts = response.css('.articleWrap ::text').getall()
        if not content_parts:
            content_parts = response.css('.narticle-data ::text, .article-content ::text').getall()
             
        # Clean up whitespace and join
        cleaned_parts = []
        for p in content_parts:
            text = p.strip()
            # Ignore javascript/css snippets or empty lines
            if text and len(text) > 1 and "{" not in text:
                cleaned_parts.append(text)
                
        if not cleaned_parts:
            # Paywall or invalid structure
            return
            
        item['content'] = "\n".join(cleaned_parts)
        
        yield item
