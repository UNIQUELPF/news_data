import scrapy
from datetime import datetime
from news_scraper.items import NewsItem
from news_scraper.utils import get_dynamic_cutoff

class AlbaniaMonitorSpider(scrapy.Spider):
    name = 'albania_monitor'
    allowed_domains = ['monitor.al']
    start_urls = ['https://monitor.al/ekonomi/']
    target_table = 'alb_monitor'

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(AlbaniaMonitorSpider, cls).from_crawler(crawler, *args, **kwargs)
        dynamic_cutoff = get_dynamic_cutoff(crawler.settings, spider.target_table)
        spider.CUTOFF_DATE = max(dynamic_cutoff, datetime(2026, 1, 1)) if dynamic_cutoff else datetime(2026, 1, 1)
        return spider

    def parse(self, response):
        """Parses the news list page."""
        # Find all article links on the listing page
        # They are usually within h3 or h2 with class d-block
        article_links = response.css('h3 a.d-block::attr(href), h2 a.d-block::attr(href)').getall()
        # Remove duplicates
        article_links = list(set(article_links))
        
        self.logger.info(f"Found {len(article_links)} article links on {response.url}")

        for href in article_links:
            yield scrapy.Request(
                url=response.urljoin(href),
                callback=self.parse_detail,
                # Pass a flag to check cutoff inside the detail page
                meta={'check_cutoff': True}
            )

        # Pagination
        next_page = response.css('.pagination li.next a::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_detail(self, response):
        """Parses the news detail page and checks cutoff."""
        # Extract precise publication date
        date_str = response.css('meta[property="article:published_time"]::attr(content)').get()
        publish_time = None
        
        if date_str:
            try:
                # Example: 2026-03-07T21:08:00+00:00
                date_str = date_str.split('+')[0] # Remove timezone for simplicity
                publish_time = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
            except Exception as e:
                self.logger.error(f"Failed to parse date {date_str} on {response.url}: {e}")
        
        if publish_time and publish_time < self.CUTOFF_DATE:
            self.logger.info(f"Reached cutoff date {self.CUTOFF_DATE} at {publish_time} on {response.url}")
            # Note: Because Scrapy requests are asynchronous, we can't easily break the pagination loop
            # from within the detail callback. However, CloseSpider extension handles graceful shutdown
            # based on item counts if needed, or we just filter out old items. To truly stop the spider
            # when reaching old items across multiple pages, a custom extension or state would be used.
            # For now, we drop the item.
            return

        item = NewsItem()
        item['url'] = response.url
        
        # Title
        item['title'] = response.css('h1::text').get(default='').strip()
        if not item['title']:
            # Fallback
            item['title'] = response.css('meta[property="og:title"]::attr(content)').get(default='')
            
        item['publish_time'] = publish_time
        item['language'] = 'sq'
        item['author'] = 'Revista Monitor'
        item['scrape_time'] = datetime.now()
        
        # Content
        content_parts = response.css('.standard-content p::text').getall()
        item['content'] = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 10])
        
        if item['content'] and item['title']:
            yield item
