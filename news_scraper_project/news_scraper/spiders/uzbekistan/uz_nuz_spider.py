import scrapy
from datetime import datetime
import re
from news_scraper.spiders.base_spider import BaseNewsSpider

class UzNuzSpider(BaseNewsSpider):
    name = 'uz_nuz'

    country_code = 'UZB'

    country = '乌兹别克斯坦'
    allowed_domains = ['nuz.uz']
    
    # 政治板块入口
    base_url = 'https://nuz.uz/category/politika/page/{}/'
    start_urls = [base_url.format(1)]
    
    # 数据库配置 (Uzbekistan -> uz, Site -> nuz)
    target_table = 'uz_nuz_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 16,
        'DOWNLOAD_DELAY': 0.5,
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_TIMEOUT': 30
    }

    def parse(self, response):
        # 1. 提取带日期的文章链接 (URL Pattern: /YYYY/MM/DD/)
        # td-module-title, td-post-title, h3 a 等均为备选
        links = response.css('a::attr(href)').getall()
        
        current_page = response.meta.get('page', 1)
        valid_items_count = 0
        
        for link in set(links):
            # 正则匹配日期指纹: /2026/03/26/
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', link)
            if date_match:
                y, m, d = date_match.groups()
                try:
                    pub_time = datetime(year=int(y), month=int(m), day=int(d))
                except:
                    continue

                # 列表页极致日期预过滤
                if not self.filter_date(pub_time):
                    continue
                
                valid_items_count += 1
                yield response.follow(
                    link, 
                    self.parse_article, 
                    meta={'pub_time': pub_time}
                )

        # 翻页逻辑
        if valid_items_count > 0 and current_page < 1000:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 提取标题
        title = response.css('h1.entry-title::text, h1::text').get('').strip()
        
        # 2. 提取发布日期 (优先使用 URL 指纹中传递过来的日期)
        pub_time = response.meta.get('pub_time')
        
        # 3. 再次确认过滤逻辑 (虽然列表页已处理，但为了严谨性增加二次检查)
        if not self.filter_date(pub_time):
            return

        # 4. 提取正文内容 (Newspaper 主题核心容器)
        content_parts = response.css('div.td-post-content p::text, div.td-post-content div::text').getall()
        content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 30])
        
        if not content:
            # 强化模式
            content = response.xpath('string(//div[contains(@class, "td-post-content")])').get()
            if not content:
                content = response.xpath('string(//article)').get()

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'News Uzbekistan (Nuz.uz)',
            'language': 'ru',
            'section': 'Politics'
        }
        
        yield item
