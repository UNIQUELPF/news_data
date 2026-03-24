import scrapy
from datetime import datetime
from news_scraper.items import NewsItem
from news_scraper.utils import get_dynamic_cutoff
import re

class AlbaniaBankSpider(scrapy.Spider):
    name = 'albania_bank'
    allowed_domains = ['bankofalbania.org']
    start_urls = ['https://www.bankofalbania.org/Shtypi/Njoftimet_per_shtyp/']
    
    target_table = 'alb_bank'

    CUTOFF_DATE = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(AlbaniaBankSpider, cls).from_crawler(crawler, *args, **kwargs)
        dynamic_cutoff = get_dynamic_cutoff(crawler.settings, spider.target_table)
        # Default starting point for newest news category
        min_cutoff = datetime(2026, 1, 1)
        spider.CUTOFF_DATE = max(dynamic_cutoff, min_cutoff) if dynamic_cutoff else min_cutoff
        return spider

    def parse(self, response):
        """Parses the press release list page."""
        # Refined selectors from precise DOM analysis
        # Items are in div.row (often without align-items-center in the source)
        rows = response.css('div.row')
        self.logger.info(f"Checking {len(rows)} potential rows on {response.url}")

        reached_cutoff = False
        scraped_in_page = 0
        for row in rows:
            # Date is in .text-dark.pb-1
            date_str = row.css('.text-dark.pb-1::text').get()
            # Title is in h5 a.text-dark.font-weight-bold
            title_node = row.css('h5 a.text-dark.font-weight-bold')
            
            if not date_str or not title_node:
                continue
                
            date_str = date_str.strip()
            title = title_node.xpath('string()').get().strip()
            href = title_node.attrib.get('href')
            
            # Date format: "04.03.2026"
            publish_time = self.parse_date(date_str)
            
            if publish_time:
                if publish_time < self.CUTOFF_DATE:
                    reached_cutoff = True
                    self.logger.info(f"Reached cutoff date {self.CUTOFF_DATE} at {publish_time}. Stopping.")
                    break
                
                scraped_in_page += 1
                yield scrapy.Request(
                    url=response.urljoin(href),
                    callback=self.parse_detail,
                    meta={'title': title, 'publish_time': publish_time}
                )

        self.logger.info(f"Scraped {scraped_in_page} items from {response.url}")

        if not reached_cutoff:
            # Pagination logic: finding the "Next" page link with Albanian title
            next_page = response.css('a.page-link[title="Faqja pasardhëse"]::attr(href)').get()
            if not next_page:
                 # Fallback to general arrows or "pasardhëse" keyword
                 next_page = response.xpath('//a[contains(@class, "page-link") and contains(@title, "pasardhëse")]/@href').get()
                 
            if next_page:
                yield response.follow(next_page, callback=self.parse)

    def parse_date(self, date_str):
        """Parses dates like '04.03.2026'."""
        try:
            match = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_str)
            if match:
                return datetime.strptime(match.group(1), '%d.%m.%Y')
        except Exception as e:
            self.logger.error(f"Error parsing date {date_str}: {e}")
        return None

    def parse_detail(self, response):
        """Parses the press release detail page."""
        item = NewsItem()
        item['url'] = response.url
        item['title'] = response.meta['title']
        item['publish_time'] = response.meta['publish_time']
        item['language'] = 'sq'
        item['author'] = 'Banka e Shqipërisë'
        item['scrape_time'] = datetime.now()
        
        # Content extraction: Confirmed selector div.fc from browser research
        content_parts = response.css('div.fc p::text, div.fc::text').getall()
        if not content_parts:
             content_parts = response.css('article p::text, div.content p::text').getall()
             
        item['content'] = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 10])
        
        if not item['content']:
            item['content'] = response.xpath('string(//div[contains(@class, "fc")])').get() or ""
            item['content'] = item['content'].strip()
            
        yield item
