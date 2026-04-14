import scrapy
import json
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class ThNationThailandSpider(BaseNewsSpider):
    name = 'th_nationthailand'

    country_code = 'THA'

    country = '泰国'
    allowed_domains = ['nationthailand.com', 'api.nationthailand.com']
    
    # 使用 API 作为起始点
    base_api_url = 'https://api.nationthailand.com/api/v1.0/categories/news?page={}'
    start_urls = [base_api_url.format(1)]
    
    # 数据库表名配置
    target_table = 'th_nationthailand_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1
    }

    def parse(self, response):
        try:
            data = json.loads(response.text)
            # 修正：真正的根节点是 'data'
            items = data.get('data', [])
        except Exception as e:
            self.logger.error(f"Failed to parse JSON API: {e}")
            return

        if not items:
            self.logger.info("No more items found in API response.")
            return

        for item in items:
            # 修正：直接使用 'link' 字段并确保指向主站 HTML 页面
            path = item.get('link')
            if path:
                # 强制使用主战域名，避免被 urljoin 到 api.nationthailand.com
                article_url = f"https://www.nationthailand.com{path}" if path.startswith('/') else path
                yield scrapy.Request(article_url, self.parse_article)

        # 翻页处理
        current_page = response.meta.get('page', 1)
        if len(items) > 0:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_api_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 提取发布时间 (ISO 格式)
        pub_time = None
        date_str = response.css('meta[property="article:published_time"]::attr(content)').get()
        if date_str:
            try:
                # 格式: 2026-03-30T15:25:00+07:00
                pub_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                pass
        
        # 备选: LD+JSON
        if not pub_time:
            ld_json = response.css('script[type="application/ld+json"]::text').get()
            if ld_json:
                try:
                    data = json.loads(ld_json)
                    if isinstance(data, list): data = data[0]
                    ds = data.get('datePublished')
                    if ds:
                        pub_time = datetime.fromisoformat(ds.replace('Z', '+00:00'))
                except:
                    pass

        if not pub_time:
            pub_time = datetime.now()

        # 2. 日期过滤
        if not self.filter_date(pub_time):
            return

        # 3. 提取内容
        title = response.css('h1::text').get('').strip()
        if not title:
            title = response.css('title::text').get('').strip()

        # 正文提取
        paragraphs = response.css('.detail p::text').getall()
        if not paragraphs:
            paragraphs = response.css('div.detail ::text').getall()
        
        content = "\n\n".join([p.strip() for p in paragraphs if p.strip()])

        # 作者
        author = response.css('meta[name="author"]::attr(content)').get() or 'Nation Thailand'

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': author,
            'language': 'en',
            'section': 'News'
        }
        
        yield item
