import scrapy
import json
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class TrSabahSpider(BaseNewsSpider):
    name = 'tr_sabah'
    allowed_domains = ['sabah.com.tr']
    
    # 初始 URL：经济新闻列表
    base_url = 'https://www.sabah.com.tr/ekonomi/{}'
    start_urls = ['https://www.sabah.com.tr/ekonomi']
    
    # 数据库表名配置
    target_table = 'tr_sabah_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'ROBOTSTXT_OBEY': False
    }

    def parse(self, response):
        # 提取文章链接
        # 排除导航链接和非详情页链接 (详情页通常带有 7 位及以上的数字 ID)
        links = response.css('a[href*="/ekonomi/"]::attr(href)').getall()
        for link in set(links):
            # 过滤掉纯分页链接
            if link.strip('/').isdigit() or link == '/ekonomi':
                continue
            
            # 详情页链接逻辑: /ekonomi/yyyy/mm/dd/title-id
            # 验证 ID 是否存在
            if '-' in link:
                yield response.follow(link, self.parse_article)

        # 翻页处理
        current_page = response.meta.get('page', 1)
        if current_page < 300: # 限制页数以回溯至 2026/1/1
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 优先从 JSON-LD 提取
        pub_time = None
        author = 'Sabah'
        title = ''
        
        ld_jsons = response.css('script[type="application/ld+json"]::text').getall()
        for ld in ld_jsons:
            try:
                data = json.loads(ld)
                if isinstance(data, list): data = data[0]
                
                # 提取核心字段
                if not title:
                    title = data.get('headline') or data.get('name')
                
                ds = data.get('datePublished')
                if ds and not pub_time:
                    # 格式: 2026-03-31T07:00:00+03:00
                    pub_time = datetime.fromisoformat(ds.replace('Z', '+00:00'))
                
                if 'author' in data:
                    auth_data = data['author']
                    if isinstance(auth_data, dict):
                        author = auth_data.get('name', author)
            except:
                continue

        # 2. 备选方案：标准 HTML 提取
        if not title:
            title = response.css('h1::text').get('').strip()
        
        if not pub_time:
            date_str = response.css('meta[property="article:published_time"]::attr(content)').get()
            if date_str:
                try:
                    pub_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    pass

        if not pub_time:
            pub_time = datetime.now()

        # 3. 日期过滤
        if not self.filter_date(pub_time):
            return

        # 4. 正文提取
        # 晨报正文主要在 .newsDetailText 或 #contextBody
        paragraphs = response.css('.newsDetailText p::text, #contextBody p::text').getall()
        if not paragraphs:
            paragraphs = response.css('.newsDetailText ::text').getall()
            
        content = "\n\n".join([p.strip() for p in paragraphs if p.strip()])

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': author,
            'language': 'tr',
            'section': 'Ekonomi'
        }
        
        yield item
