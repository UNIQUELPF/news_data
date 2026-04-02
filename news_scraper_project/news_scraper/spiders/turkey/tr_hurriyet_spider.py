import scrapy
import json
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class TrHurriyetSpider(BaseNewsSpider):
    name = 'tr_hurriyet'
    allowed_domains = ['hurriyet.com.tr']
    
    # 初始 URL：时政新闻列表
    base_url = 'https://www.hurriyet.com.tr/gundem/?p={}'
    start_urls = [base_url.format(1)]
    
    # 数据库表名配置
    target_table = 'tr_hurriyet_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'ROBOTSTXT_OBEY': False
    }

    def parse(self, response):
        # 提取文章链接
        # 列表项通常具有 category__list__item 类
        links = response.css('.category__list__item a::attr(href)').getall()
        if not links:
            # 备选提取方式
            links = response.css('a[href*="/gundem/"]::attr(href)').getall()

        for link in set(links):
            # 排除分页链接和非文章链接
            if '?p=' in link or link == '/gundem/':
                continue
            yield response.follow(link, self.parse_article)

        # 翻页处理
        current_page = response.meta.get('page', 1)
        if current_page < 500: # 限制页数以回溯至 2026/1/1
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 优先从 JSON-LD 提取 (最稳健，无视语言干扰)
        pub_time = None
        author = 'Hurriyet'
        title = ''
        
        ld_jsons = response.css('script[type="application/ld+json"]::text').getall()
        for ld in ld_jsons:
            try:
                data = json.loads(ld)
                # 处理数组或对象格式
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
                    elif isinstance(auth_data, list):
                        author = auth_data[0].get('name', author)
            except:
                continue

        # 2. 备选方案：标准 HTML 提取
        if not title:
            title = response.css('h1::text, .news-article__title::text').get('').strip()
        
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
        # 自由报正文通常在 .news-content 或 .article-body
        paragraphs = response.css('.news-content p::text, .article-content p::text').getall()
        if not paragraphs:
            paragraphs = response.css('.news-content ::text').getall()
            
        content = "\n\n".join([p.strip() for p in paragraphs if p.strip()])

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': author,
            'language': 'tr',
            'section': 'Gündem'
        }
        
        yield item
