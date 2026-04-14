import scrapy
from datetime import datetime
import re
from news_scraper.spiders.base_spider import BaseNewsSpider

class GrTovimaSpider(BaseNewsSpider):
    name = 'gr_tovima'

    country_code = 'GRC'

    country = '希腊'
    allowed_domains = ['tovima.gr']
    
    # 论坛报财经板块
    base_url = 'https://www.tovima.gr/category/finance/page/{}/'
    start_urls = [base_url.format(1)]
    
    # 数据库配置 (Greece -> gr, Site -> tovima)
    target_table = 'gr_tovima_news'

    def parse(self, response):
        # 1. 提取所有可能的文章链接
        # 探测结果显示 a.is-block 和 a.columns.is-mobile.is-multiline 是链接载体
        links = response.css('a.is-block::attr(href), a.columns.is-mobile.is-multiline::attr(href)').getall()
        
        current_page = response.meta.get('page', 1)
        valid_items_count = 0
        
        for link in links:
            # 2. URL 日期指纹初筛: /2026/03/30/
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', link)
            if date_match:
                year, month, day = date_match.groups()
                try:
                    url_date = datetime(year=int(year), month=int(month), day=int(day))
                    if not self.filter_date(url_date):
                        continue
                except:
                    pass

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
            # 格式: 2026-03-30T10:30:48+00:00
            pub_time = datetime.fromisoformat(pub_time_raw.split('+')[0])
        except:
            return

        # 2. 日期过滤 (2026-01-01 之后)
        if not self.filter_date(pub_time):
            return

        # 3. 提取标题和内容
        title = response.css('h1.entry-title::text').get('').strip()
        # 正文通常在 article 下的 p 标签
        content_parts = response.css('article p::text').getall()
        content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 20])

        if not content:
            # 兜底选择器
            content = "\n\n".join(response.css('.post-content p::text').getall())

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'To Vima Finance',
            'language': 'el',
            'section': 'Finance'
        }
        
        yield item
