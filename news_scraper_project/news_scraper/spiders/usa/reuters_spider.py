import scrapy
from news_scraper.spiders.base_spider import BaseNewsSpider

class USAReutersSpider(BaseNewsSpider):
    name = 'usa_reuters'
    allowed_domains = ['reuters.com']
    
    # 继承 BaseNewsSpider，自动初始化 usa_reuters_news 表
    target_table = 'usa_reuters_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # 初始请求 sections 为了历史回溯
        sections = ['business/finance', 'markets/us', 'world/us']
        for sec in sections:
            api_url = f"https://www.reuters.com/pf/api/v1/json/articles-by-section-v1?latest=true&size=50&offset=0&section={sec}"
            yield scrapy.Request(api_url, callback=self.parse_api, meta={'section': sec, 'offset': 0})

    def parse_api(self, response):
        data = response.json()
        articles = data.get('result', {}).get('articles', [])
        if not articles:
            return

        for art in articles:
            url = f"https://www.reuters.com{art.get('canonical_url')}"
            pub_time_str = art.get('display_date')
            from datetime import datetime
            try:
                pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00')).replace(tzinfo=None)
            except:
                pub_time = None

            # 使用基类日期过滤
            if not self.filter_date(pub_time):
                continue
                
            yield scrapy.Request(url, callback=self.parse_article, meta={'pub_time': pub_time})

        # 翻页逻辑
        offset = response.meta['offset'] + 50
        section = response.meta['section']
        if len(articles) >= 50:
            next_url = f"https://www.reuters.com/pf/api/v1/json/articles-by-section-v1?latest=true&size=50&offset={offset}&section={section}"
            yield scrapy.Request(next_url, callback=self.parse_api, meta={'section': section, 'offset': offset})

    def parse_article(self, response):
        from bs4 import BeautifulSoup
        title = response.css('h1::text').get()
        # 简单清洗正文
        body = response.css('div.article-body__content').get()
        content = ""
        if body:
            soup = BeautifulSoup(body, 'html.parser')
            content = "\n\n".join([p.get_text().strip() for p in soup.find_all('p') if len(p.get_text()) > 20])

        yield {
            'url': response.url,
            'title': title.strip() if title else 'Unknown',
            'content': content,
            'publish_time': response.meta['pub_time'],
            'author': 'Reuters',
            'language': 'en',
            'section': 'USA Finance',
        }
