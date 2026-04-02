import scrapy
import json
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class TrHaberturkSpider(BaseNewsSpider):
    name = 'tr_haberturk'
    allowed_domains = ['haberturk.com']
    
    # 无限加载接口
    base_url = 'https://www.haberturk.com/infinite/ekonomi/tumhaberler/p{}'
    start_urls = [base_url.format(1)]
    
    # 数据库表名配置
    target_table = 'tr_haberturk_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'ROBOTSTXT_OBEY': False
    }

    def parse(self, response):
        # 提取文章链接
        # Habertürk 的无限加载返回的是 HTML 片段
        links = response.css('a.block::attr(href)').getall()
        
        # 过滤广告和非相关链接
        valid_links = []
        for link in set(links):
            # 详情页通常包含 ID-ekonomi 或 ID-teknoloji 结尾
            if '-ekonomi' in link or any(char.isdigit() for char in link.split('-')[-1]):
                valid_links.append(link)

        for link in valid_links:
            yield response.follow(link, self.parse_article)

        # 只要当前页有数据返回，就继续翻页
        if links:
            current_page = response.meta.get('page', 1)
            if current_page < 500: # 限制页数以回溯至 2026/1/1
                next_page = current_page + 1
                yield scrapy.Request(
                    self.base_url.format(next_page),
                    callback=self.parse,
                    meta={'page': next_page}
                )

    def parse_article(self, response):
        # 1. 优先从 JSON-LD 提取 (最精准)
        pub_time = None
        author = 'Haberturk'
        title = ''
        content = ''
        
        ld_jsons = response.css('script[type="application/ld+json"]::text').getall()
        for ld in ld_jsons:
            try:
                data = json.loads(ld)
                # 处理数组或嵌套对象
                if isinstance(data, list): data = data[0]
                if '@graph' in data: data = data['@graph'][0]
                
                # 提取标题
                if not title:
                    title = data.get('headline') or data.get('name')
                
                # 提取日期
                ds = data.get('datePublished')
                if ds and not pub_time:
                    # 格式: 2026-02-21T18:47:49+03:00
                    pub_time = datetime.fromisoformat(ds.replace('Z', '+00:00'))
                
                # 提取正文
                if not content:
                    content = data.get('articleBody', '')
                
                # 提取作者
                if 'author' in data:
                    auth_data = data['author']
                    if isinstance(auth_data, dict):
                        author = auth_data.get('name', author)
            except:
                continue

        # 2. 备选方案：标准 HTML 提取 (如果 JSON-LD 缺失)
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

        # 4. 如果 JSON-LD 中没拿到正文，则从 HTML 提取
        if not content:
            paragraphs = response.css('.newsDetailText p::text, article p::text').getall()
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
