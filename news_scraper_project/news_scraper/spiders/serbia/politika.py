# 塞尔维亚politika爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from datetime import datetime
from news_scraper.items import NewsItem
from news_scraper.utils import get_dynamic_cutoff

class PolitikaSpider(scrapy.Spider):
    name = 'politika'

    country_code = 'SRB'

    country = '塞尔维亚'
    allowed_domains = ['politika.rs']
    start_urls = ['https://www.politika.rs/scc/columns/archive/6']
    
    target_table = 'ser_politika'

    custom_settings = {
        'ROBOTSTXT_OBEY': False
    }

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(PolitikaSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider.CUTOFF_DATE = get_dynamic_cutoff(crawler.settings, spider.target_table, spider_name=spider.name)
        return spider

    def parse(self, response):
        items = response.css('.column-data .news-item')
        
        for item in items:
            title_tag = item.css('h3.h3 a')
            url = title_tag.attrib.get('href')
            title = title_tag.css('::text').get().strip()

            if url:
                full_url = response.urljoin(url)
                yield scrapy.Request(
                    full_url, 
                    callback=self.parse_detail, 
                    meta={'title': title}
                )

        # Pagination
        current_page_num = response.meta.get('page', 1)
        next_page_num = current_page_num + 1
        
        if items:
            next_url = f"https://www.politika.rs/scc/columns/archive/6/page:{next_page_num}?url="
            yield scrapy.Request(
                next_url, 
                callback=self.parse, 
                meta={'page': next_page_num}
            )

    def parse_detail(self, response):
        publish_time_str = response.css('span[itemprop="datePublished"]::attr(content)').get()
        
        if publish_time_str:
            try:
                dt_str = publish_time_str.split('+')[0]
                publish_time = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
            except Exception as e:
                self.logger.error(f"Error parsing date {publish_time_str}: {e}")
                return

            if publish_time < self.CUTOFF_DATE:
                self.logger.info(f"Reached cutoff date: {publish_time}")
                return

            item = NewsItem()
            item['url'] = response.url
            item['title'] = response.meta['title']
            item['publish_time'] = publish_time
            
            content_parts = response.css('#text-holder p::text, #text-holder p span::text').getall()
            if not content_parts:
                content_parts = response.css('.article-content p::text, .article-content p span::text').getall()
                
            item['content'] = "\n".join([p.strip() for p in content_parts if p.strip()])
            
            author = response.css('.article-author::text, .article-info .bold::text').get()
            item['author'] = author.strip() if author else "Politika"
            item['language'] = 'sr'
            item['scrape_time'] = datetime.now()
            
            yield item
