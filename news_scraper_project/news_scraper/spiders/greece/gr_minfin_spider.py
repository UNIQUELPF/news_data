import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class GrMinfinSpider(BaseNewsSpider):
    name = 'gr_minfin'
    allowed_domains = ['minfin.gov.gr']
    
    # 财政部新闻大厅
    base_url = 'https://minfin.gov.gr/grafeio-typou/anakoinoseis-typou-el/page/{}/'
    start_urls = [base_url.format(1)]
    
    # 数据库配置 (Greece -> gr, Site -> minfin)
    target_table = 'gr_minfin_news'

    def parse(self, response):
        # 1. 提取所有 Elementor 新闻块
        # 探测结果: .elementor-post__title a
        articles = response.css('.elementor-post__title a')
        
        current_page = response.meta.get('page', 1)
        valid_items_count = 0
        
        for art in articles:
            link = art.css('::attr(href)').get()
            if not link:
                continue
                
            valid_items_count += 1
            yield response.follow(link, self.parse_article)

        # 2. 翻页逻辑
        # 希腊财政部翻页深广，支持 2026/01/01 回溯
        if valid_items_count > 0 and current_page < 1000:
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
            # 兜底从 body 提取 (elementor-post-info__item--type-date)
            # 这里我们坚持使用 meta 标签以确保 ISO 格式
            return

        try:
            # 格式: 2026-03-27T14:57:13+00:00
            pub_time = datetime.fromisoformat(pub_time_raw.split('+')[0])
        except:
            return

        # 2. 日期过滤 (2026-01-01 之后)
        if not self.filter_date(pub_time):
            return

        # 3. 提取标题和内容
        title = response.css('h1.elementor-heading-title::text, h1::text').get('').strip()
        
        # 探测显示正文容器: .elementor-widget-theme-post-content .elementor-widget-container
        content_parts = response.css('.elementor-widget-theme-post-content .elementor-widget-container p::text').getall()
        content = "\n\n".join([p.strip() for p in content_parts if p.strip()])

        if not content:
            # 兜底选择器
            content = "\n\n".join(response.css('div.elementor-widget-container p::text').getall())

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'Ministry of Finance Greece',
            'language': 'el',
            'section': 'Press Office'
        }
        
        yield item
