import scrapy
from datetime import datetime
import re
from news_scraper.spiders.base_spider import BaseNewsSpider

class GrKathimeriniSpider(BaseNewsSpider):
    name = 'gr_kathimerini'
    allowed_domains = ['kathimerini.gr']
    
    # 航运报经济板块
    base_url = 'https://www.kathimerini.gr/economy/local/page/{}/'
    start_urls = [base_url.format(1)]
    
    # 数据库配置 (Greece -> gr, Site -> kathimerini)
    target_table = 'gr_kathimerini_news'

    def parse(self, response):
        # 1. 提取所有卡片
        cards = response.css('div.card')
        
        current_page = response.meta.get('page', 1)
        valid_items_count = 0
        
        for card in cards:
            link = card.css('a::attr(href)').get()
            date_str = card.css('.card-date::text').get()
            
            if not link or not date_str:
                continue

            # 2. 列表页日期初筛 (格式: 31.03.2026)
            try:
                date_clean = date_str.strip()
                day, month, year = date_clean.split('.')
                list_date = datetime(year=int(year), month=int(month), day=int(day))
            except:
                continue

            if not self.filter_date(list_date):
                continue
            
            valid_items_count += 1
            yield response.follow(link, self.parse_article)

        # 3. 翻页逻辑
        if valid_items_count > 0 and current_page < 5000:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 提取发布时间 (ISO 优先)
        pub_time_raw = response.css('meta[property="article:published_time"]::attr(content)').get()
        
        if not pub_time_raw:
            return

        try:
            # 格式: 2026-03-30T15:05:23+03:00
            pub_time = datetime.fromisoformat(pub_time_raw.split('+')[0])
        except:
            return

        # 2. 日期过滤 (2026-01-01 之后)
        if not self.filter_date(pub_time):
            return

        # 3. 提取标题和内容
        title = response.css('h1::text').get('').strip()
        content_parts = response.css('.entry-content p::text').getall()
        content = "\n\n".join([p.strip() for p in content_parts if p.strip()])

        if not content:
            content = "\n\n".join(response.css('article p::text').getall())

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'Kathimerini Economy',
            'language': 'el',
            'section': 'Economy/Local'
        }
        
        yield item
