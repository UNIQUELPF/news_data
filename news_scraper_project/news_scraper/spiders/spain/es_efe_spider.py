import scrapy
from datetime import datetime
import re
from news_scraper.spiders.base_spider import BaseNewsSpider

class EsEfeSpider(BaseNewsSpider):
    name = 'es_efe'
    allowed_domains = ['efe.com']
    
    # 埃菲社板块
    base_url = 'https://efe.com/portada-espana/page/{}/'
    start_urls = [base_url.format(1)]
    
    target_table = 'es_efe_news'
    
    custom_settings = {
        'DOWNLOAD_DELAY': 3.0, 
        'CONCURRENT_REQUESTS': 2,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 101,  # 确保中间层激活
            'news_scraper.middlewares.BatchDelayMiddleware': 600,
        },
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    }

    def start_requests(self):
        for url in self.start_urls:
            # 关键：指定 CurlCffi 模拟指纹
            yield scrapy.Request(
                url, 
                meta={'impersonate': 'chrome110', 'page_idx': 1}
            )

    def parse(self, response):
        # 调试
        self.logger.info(f"PARSE_TRIGGERED: {response.url}, Title: {response.css('title::text').get()}")
        
        # 1. 提取新闻链接 (基于 WP 结构，结合图片审计)
        # 链接格式: .../espana/YYYY-MM-DD/slug/
        articles = response.css('h2.entry-title a, article a[href*="/2026-"]')
        
        current_page = response.meta.get('page_idx', 1)
        valid_items_count = 0
        
        for art in articles:
            # 兼容 data-mrf-link 
            link = art.css('::attr(data-mrf-link)').get() or art.css('::attr(href)').get()
            if not link: continue
            
            absolute_link = response.urljoin(link)
            
            # 日期正则检测
            date_match = re.search(r'/(\d{4})-(\d{2})-(\d{2})/', absolute_link)
            if date_match:
                y, m, d = date_match.groups()
                try:
                    pub_time = datetime(year=int(y), month=int(m), day=int(d))
                except: continue

                if not self.filter_date(pub_time): continue
                
                valid_items_count += 1
                yield response.follow(
                    absolute_link, 
                    self.parse_article, 
                    meta={'pub_time': pub_time, 'impersonate': 'chrome110'}
                )

        # 翻页
        if (valid_items_count > 0 or current_page < 3) and current_page < 3000:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page_idx': next_page, 'impersonate': 'chrome110'}
            )

    def parse_article(self, response):
        title = response.css('h1.entry-title::text, h1::text').get('').strip()
        pub_time = response.meta.get('pub_time')
        if not self.filter_date(pub_time): return

        # 提取正文内容
        content_parts = response.css('div.entry-content p::text, div.content-column p::text, div.p-body p::text').getall()
        content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 30])
        
        if not content:
            # 兜底容器
            content = response.xpath('string(//div[contains(@class, "inside-article")] | //article)').get()

        item = {
            'url': response.url, 'title': title, 'content': content,
            'publish_time': pub_time, 'author': 'EFE News', 'language': 'es', 'section': 'España'
        }
        yield item
