import scrapy
import json
import re
from datetime import datetime
from news_scraper.items import NewsItem
from news_scraper.utils import get_dynamic_cutoff

class AlbaniaAtaSpider(scrapy.Spider):
    name = "albania_ata"
    allowed_domains = ["ata.gov.al"]
    target_table = "alb_ata"
    
    # Category 47 is 'Ekonomi'
    base_url = "https://ata.gov.al/wp-json/wp/v2/posts?categories=47&per_page=100"
    
    def __init__(self, *args, **kwargs):
        super(AlbaniaAtaSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime(2026, 1, 1)

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(AlbaniaAtaSpider, cls).from_crawler(crawler, *args, **kwargs)
        # For incremental crawl, get the latest date from DB if needed
        # dynamic_cutoff = get_dynamic_cutoff(crawler.settings, spider.target_table)
        # spider.cutoff_date = dynamic_cutoff
        return spider

    def start_requests(self):
        # Start from page 1
        url = f"{self.base_url}&after={self.cutoff_date.strftime('%Y-%m-%dT%H:%M:%SZ')}&page=1"
        yield scrapy.Request(url, callback=self.parse, meta={'page': 1})

    def parse(self, response):
        try:
            posts = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
            return

        if not posts:
            self.logger.info("No more posts found.")
            return

        for post in posts:
            item = NewsItem()
            item['url'] = post.get('link')
            item['title'] = post.get('title', {}).get('rendered')
            
            # Clean HTML from title if any
            if item['title']:
                item['title'] = re.sub(r'<[^>]+>', '', item['title']).strip()
                
            # Content is rendered HTML
            # We preserve basics but can clean if needed. 
            # The user asked for "content", we usually keep it clean but readable.
            raw_content = post.get('content', {}).get('rendered', '')
            item['content'] = re.sub(r'<[^>]+>', '', raw_content).strip()
            
            # Publish time
            date_str = post.get('date') # Format: 2026-03-11T09:26:20
            if date_str:
                item['publish_time'] = datetime.fromisoformat(date_str)
            
            item['author'] = str(post.get('author'))
            item['language'] = 'Albanian'
            
            yield item

        # Pagination
        current_page = response.meta.get('page', 1)
        # X-WP-TotalPages header tells us how many pages there are
        total_pages = int(response.headers.get('X-WP-TotalPages', 0))
        
        if current_page < total_pages:
            next_page = current_page + 1
            next_url = f"{self.base_url}&after={self.cutoff_date.strftime('%Y-%m-%dT%H:%M:%SZ')}&page={next_page}"
            yield scrapy.Request(next_url, callback=self.parse, meta={'page': next_page})
