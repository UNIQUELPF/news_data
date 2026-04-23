import scrapy
import json
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider
from pipeline.content_engine import ContentEngine

class AlbaniaAtaSpider(SmartSpider):
    """
    Albania ATA Spider using WP-JSON API.
    Extracts article content directly from JSON responses,
    avoiding 403 blocks on article HTML pages.
    """
    name = "albania_ata"
    source_timezone = 'Europe/Tirane'
    
    country_code = 'ALB'
    country = '阿尔巴尼亚'
    
    allowed_domains = ["ata.gov.al"]
    
    # Category 47 is 'Ekonomi'
    base_url = "https://ata.gov.al/wp-json/wp/v2/posts?categories=47&per_page=100"
    
    async def start(self):
        url = f"{self.base_url}&after={self.cutoff_date.strftime('%Y-%m-%dT%H:%M:%SZ')}&page=1"
        yield scrapy.Request(url, callback=self.parse, meta={'page': 1}, dont_filter=True)

    def parse(self, response):
        try:
            posts = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
            return

        if not posts:
            self.logger.info("No more posts found.")
            return

        has_valid_item_in_window = False
        for post in posts:
            url = post.get('link')
            
            # Publish time from JSON
            date_str = post.get('date')  # Format: 2026-03-11T09:26:20
            publish_time = None
            if date_str:
                publish_time = self.parse_to_utc(datetime.fromisoformat(date_str))
            
            if not self.should_process(url, publish_time):
                continue
            
            has_valid_item_in_window = True
            
            # Extract title from JSON
            title = post.get('title', {}).get('rendered', '').strip()
            # Clean HTML entities from title
            title = re.sub(r'<[^>]+>', '', title)
            
            # Extract content HTML from JSON
            content_html = post.get('content', {}).get('rendered', '')
            
            if not content_html:
                self.logger.warning(f"Empty content for {url}, skipping")
                continue
            
            # Use ContentEngine to process the HTML content
            content_data = ContentEngine.process(
                raw_html=f"<html><body>{content_html}</body></html>",
                base_url=url
            )
            
            # Assemble the item directly
            item = {
                "url": url,
                "title": title,
                "raw_html": content_html,
                "publish_time": publish_time,
                "language": getattr(self, 'language', 'en'),
                "section": "news",
                "country_code": self.country_code,
                "country": self.country,
                **content_data
            }
            
            self.logger.info(f"Extracted from JSON: {title[:60]}...")
            yield item

        # Pagination
        if has_valid_item_in_window:
            current_page = response.meta.get('page', 1)
            total_pages = int(response.headers.get('X-WP-TotalPages', 0))
            if current_page < total_pages:
                next_page = current_page + 1
                next_url = f"{self.base_url}&after={self.cutoff_date.strftime('%Y-%m-%dT%H:%M:%SZ')}&page={next_page}"
                yield scrapy.Request(next_url, callback=self.parse, meta={'page': next_page}, dont_filter=True)
