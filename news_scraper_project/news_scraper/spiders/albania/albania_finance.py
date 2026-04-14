# 阿尔巴尼亚finance爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from datetime import datetime
import re
from news_scraper.items import NewsItem
from news_scraper.utils import get_dynamic_cutoff

class AlbaniaFinanceSpider(scrapy.Spider):
    name = 'albania_finance'

    country_code = 'ALB'

    country = '阿尔巴尼亚'
    allowed_domains = ['financa.gov.al']
    start_urls = ['https://financa.gov.al/newsrooms/lajme/']
    target_table = 'alb_financa'

    albanian_months = {
        'janar': 1, 'shkurt': 2, 'mars': 3, 'prill': 4,
        'maj': 5, 'qershor': 6, 'korrik': 7, 'gusht': 8,
        'shtator': 9, 'tetor': 10, 'nëntor': 11, 'dhjetor': 12
    }

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(AlbaniaFinanceSpider, cls).from_crawler(crawler, *args, **kwargs)
        dynamic_cutoff = get_dynamic_cutoff(crawler.settings, spider.target_table, spider_name=spider.name)
        # We want to crawl at least from 2026-01-01
        min_cutoff = datetime(2026, 1, 1)
        spider.CUTOFF_DATE = max(dynamic_cutoff, min_cutoff) if dynamic_cutoff else min_cutoff
        return spider

    def parse(self, response):
        """Parses the news list page."""
        # Containers identified by browser subagent
        items = response.css('.horizontal-news-item')
        self.logger.info(f"Found {len(items)} news items on {response.url}")

        reached_cutoff = False
        for item_node in items:
            title_node = item_node.css('a.news-item__title')
            href = title_node.attrib.get('href')
            title = title_node.xpath('string()').get().strip()
            
            # Date is typically in a separate div or span within the horizontal-news-item
            # Subagent said it follows "POSTUAR MË:"
            date_text = item_node.css('.news-item__date::text, span::text, div::text').getall()
            date_str = " ".join(date_text).strip()
            
            publish_time = self.parse_alb_date(date_str)
            
            if publish_time:
                if publish_time < self.CUTOFF_DATE:
                    reached_cutoff = True
                    self.logger.info(f"Reached cutoff {self.CUTOFF_DATE} at {publish_time}. Stopping.")
                    break
                
                yield scrapy.Request(
                    url=response.urljoin(href),
                    callback=self.parse_detail,
                    meta={'title': title, 'publish_time': publish_time}
                )

        if not reached_cutoff:
            # Pagination: .pagination a.page-numbers.next
            next_page = response.css('a.next.page-numbers::attr(href)').get()
            if next_page:
                yield response.follow(next_page, callback=self.parse)

    def parse_alb_date(self, date_str):
        """Parses Albanian dates like '5 Mars 2026' or 'POSTUAR MË: 5 Mars 2026'."""
        try:
            # Normalize and lowercase
            date_str = date_str.lower().replace('postuar më:', '').strip()
            # Regex for "D Month YYYY"
            match = re.search(r'(\d{1,2})\s+([a-zë]+)\s+(\d{4})', date_str)
            if match:
                day = int(match.group(1))
                month_name = match.group(2)
                year = int(match.group(3))
                
                month = self.albanian_months.get(month_name)
                if month:
                    return datetime(year, month, day)
        except Exception as e:
            self.logger.error(f"Error parsing date {date_str}: {e}")
        return None

    def parse_detail(self, response):
        """Parses the news detail page."""
        item = NewsItem()
        item['url'] = response.url
        item['title'] = response.meta['title']
        item['publish_time'] = response.meta['publish_time']
        item['language'] = 'sq'
        item['author'] = 'Ministria e Financave'
        item['scrape_time'] = datetime.now()
        
        # Content extraction: identified as being within <article>
        content_parts = response.css('article p::text, article div.entry-content p::text').getall()
        if not content_parts:
            # Fallback to main content area
            content_parts = response.css('div.post-content p::text').getall()
            
        item['content'] = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 10])
        
        if not item['content']:
            # Ultimate fallback
            item['content'] = response.xpath('string(//article)').get() or ""
            item['content'] = item['content'].strip()
            
        yield item
