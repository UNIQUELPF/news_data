import scrapy
from datetime import datetime
import re
import json
from news_scraper.spiders.base_spider import BaseNewsSpider

class EsElconfidencialSpider(BaseNewsSpider):
    name = 'es_elconfidencial'
    allowed_domains = ['elconfidencial.com']
    
    # 实时新闻入口。结合探测，尝试 ?page=X 和 /pX/ 的兼容性
    base_url = 'https://www.elconfidencial.com/ultima-hora-en-vivo/?page={}'
    start_urls = [base_url.format(1)]
    
    # 数据库配置 (Spain -> es, Site -> elconfidencial)
    target_table = 'es_elconfidencial_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 16,
        'DOWNLOAD_DELAY': 0.5,
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_TIMEOUT': 40
    }

    def parse(self, response):
        # 1. 提取所有链接，并正则匹配日期指纹: /YYYY-MM-DD/
        all_links = response.css('a::attr(href)').getall()
        
        current_page = response.meta.get('page', 1)
        valid_items_count = 0
        
        # 使用 set 去重
        for link in set(all_links):
            # 完整 URL 为: .../2026-03-31/slug/
            date_match = re.search(r'/(\d{4})-(\d{2})-(\d{2})/', link)
            if date_match:
                y, m, d = date_match.groups()
                try:
                    pub_time = datetime(year=int(y), month=int(m), day=int(d))
                except:
                    continue

                # 列表页秒级日期过滤
                if not self.filter_date(pub_time):
                    continue
                
                valid_items_count += 1
                yield response.follow(
                    link, 
                    self.parse_article, 
                    meta={'pub_time': pub_time}
                )

        # 翻页逻辑
        # 如果当前页能抓到有效日期，且页数在安全范围内，继续
        if valid_items_count > 0 and current_page < 1000:
            next_page = current_page + 1
            # 尝试接力请求第 X 页
            # El Confidencial 翻页可能需要特定标识
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 提取标题
        title = response.css('h1::text').get('').strip()
        
        # 2. 提取日期 (优先使用 URL 解析出来的日期)
        pub_time = response.meta.get('pub_time')
        
        # 3. 日期过滤
        if not self.filter_date(pub_time):
            return

        # 4. 提取正文内容
        # 该站点正文类名多变，组合提取以确保 100% 捕获率
        content_parts = response.css('div.news-body p::text, div.p-body p::text, div.article-body p::text, div#news-body-content p::text').getall()
        content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 30])
        
        if not content:
            # 极速探测模式下的兜底正文选择器
            content = response.xpath('string(//div[contains(@class, "news-body")])').get()
            if not content:
                content = response.xpath('string(//article)').get()

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': response.css('span[class*="author"]::text, .signature__name::text').get('ABC News').strip(),
            'language': 'es',
            'section': 'Última Hora'
        }
        
        yield item
