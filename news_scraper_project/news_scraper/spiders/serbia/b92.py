# 塞尔维亚b92爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from datetime import datetime
from news_scraper.items import NewsItem
from news_scraper.utils import get_dynamic_cutoff
import re

class B92Spider(scrapy.Spider):
    name = 'b92'

    country_code = 'SRB'

    country = '塞尔维亚'
    allowed_domains = ['b92.net']
    start_urls = ['https://www.b92.net/najnovije-vesti']
    
    target_table = 'ser_b92'

    custom_settings = {
        'ROBOTSTXT_OBEY': False
    }

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(B92Spider, cls).from_crawler(crawler, *args, **kwargs)
        spider.CUTOFF_DATE = get_dynamic_cutoff(crawler.settings, spider.target_table, spider_name=spider.name)
        return spider

    def parse(self, response):
        items = response.css('.news-item-data')
        
        for item in items:
            title_tag = item.css('h2.news-item-title a')
            url = title_tag.attrib.get('href')
            title = "".join(title_tag.css('span::text').getall()).strip()
            if not title:
                title = title_tag.css('::text').get().strip()

            date_str = item.css('.news-item-date::text').get()
            hour_str = item.css('.news-item-hour::text').get()

            if date_str and hour_str:
                publish_time = self.parse_sr_date(date_str.strip(), hour_str.strip())
                
                if publish_time:
                    if publish_time < self.CUTOFF_DATE:
                        self.logger.info(f"Reached cutoff date: {publish_time}")
                        return

                    if url:
                        full_url = response.urljoin(url)
                        yield scrapy.Request(
                            full_url, 
                            callback=self.parse_detail, 
                            meta={'title': title, 'publish_time': publish_time}
                        )

        # Pagination
        next_page = response.css('ul.pagination li.page-item a.page-link[href*="page="]::attr(href)').getall()
        current_page_match = re.search(r'page=(\d+)', response.url)
        current_page = int(current_page_match.group(1)) if current_page_match else 1
        
        target_page = current_page + 1
        for link in next_page:
            if f"page={target_page}" in link:
                yield response.follow(link, self.parse)
                break

    def parse_detail(self, response):
        item = NewsItem()
        item['url'] = response.url
        item['title'] = response.meta['title']
        item['publish_time'] = response.meta['publish_time']
        
        content_parts = response.css('#article-content p::text, #article-content p span::text').getall()
        item['content'] = "\n".join([p.strip() for p in content_parts if p.strip()])
        
        author = response.css('.article-author::text').get()
        item['author'] = author.strip() if author else "B92"
        item['language'] = 'sr'
        item['scrape_time'] = datetime.now()
        
        yield item

    def parse_sr_date(self, date_str, hour_str):
        try:
            date_clean = date_str.rstrip('.')
            full_str = f"{date_clean} {hour_str}"
            return datetime.strptime(full_str, "%d.%m.%Y %H:%M")
        except Exception as e:
            self.logger.error(f"Error parsing date {date_str} {hour_str}: {e}")
            return None
