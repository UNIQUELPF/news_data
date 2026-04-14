# 阿尔巴尼亚albania爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from datetime import datetime
from news_scraper.items import NewsItem
from news_scraper.utils import get_dynamic_cutoff
import re

# NOTE: This site has strong Incapsula protection. 
# Initial historical data (2026-01-01 to 2026-03-09) was crawled via Browser Subagent.
# This spider contains the parsing logic but may require a headful browser or proxy to run.

class AlbaniaSpider(scrapy.Spider):
    name = 'albania'

    country_code = 'ALB'

    country = '阿尔巴尼亚'
    allowed_domains = ['kryeministria.al']
    start_urls = ['https://www.kryeministria.al/newsrooms/lajme/']
    
    target_table = 'alb_news'

    # Albanian month mapping
    ALB_MONTHS = {
        'janar': 1, 'shkurt': 2, 'mars': 3, 'prill': 4,
        'maj': 5, 'qershor': 6, 'korrik': 7, 'gusht': 8,
        'shtator': 9, 'tetor': 10, 'nëntor': 11, 'dhjetor': 12
    }

    CUTOFF_DATE = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(AlbaniaSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider.CUTOFF_DATE = get_dynamic_cutoff(crawler.settings, spider.target_table, spider_name=spider.name)
        return spider

    def parse(self, response):
        """Parses the news list page."""
        articles = response.css('article.news-item')
        self.logger.info(f"Scraping {len(articles)} articles from {response.url}")

        reached_cutoff = False
        for article in articles:
            title_node = article.css('a.news-item__title')
            date_node = article.css('time.posted-on')
            
            if title_node and date_node:
                title = title_node.xpath('string()').get().strip()
                href = title_node.attrib.get('href')
                date_str = date_node.xpath('string()').get().strip()
                
                # Format example: "Postuar më: 19 Shkurt 2026"
                publish_time = self.parse_alb_date(date_str)
                
                if publish_time:
                    if publish_time < self.CUTOFF_DATE:
                        reached_cutoff = True
                        self.logger.info(f"Reached cutoff date {self.CUTOFF_DATE} at {publish_time}. Stopping.")
                        break
                    
                    yield scrapy.Request(
                        url=response.urljoin(href),
                        callback=self.parse_detail,
                        meta={'title': title, 'publish_time': publish_time}
                    )

        if not reached_cutoff:
            next_page = response.css('a.nextpostslink::attr(href)').get()
            if next_page:
                yield response.follow(next_page, callback=self.parse)

    def parse_alb_date(self, date_str):
        """Parses Albanian date strings like 'Postuar më: 19 Shkurt 2026'."""
        try:
            clean_str = date_str.lower().replace('postuar më:', '').strip()
            parts = clean_str.split()
            if len(parts) >= 3:
                day = int(parts[0])
                month_name = parts[1]
                year = int(parts[2])
                
                month = self.ALB_MONTHS.get(month_name)
                if month:
                    return datetime(year, month, day)
        except Exception as e:
            self.logger.error(f"Error parsing date {date_str}: {e}")
        return None

    def parse_detail(self, response):
        """Parses the article detail page."""
        item = NewsItem()
        item['url'] = response.url
        item['title'] = response.meta['title']
        item['publish_time'] = response.meta['publish_time']
        item['language'] = 'sq'
        item['author'] = 'Kryeministria Shqiptare'
        item['scrape_time'] = datetime.now()
        
        # Content extraction: paragraphs within article
        content_parts = response.css('article p::text').getall()
        content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 10])
        
        if not content:
            article_body = response.css('div.body-content, div.container1')
            content = article_body.xpath('string()').get().strip()
            
        item['content'] = content
        yield item
