import scrapy
import json
import psycopg2
from datetime import datetime
from bs4 import BeautifulSoup
from news_scraper.settings import POSTGRES_SETTINGS

class USAArsTechnicaSpider(scrapy.Spider):
    name = 'usa_arstechnica'
    allowed_domains = ['arstechnica.com']
    start_urls = ['https://arstechnica.com/']
    
    target_table = 'usa_arstechnica_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    def __init__(self, start_date='2026-01-01', *args, **kwargs):
        super(USAArsTechnicaSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime.strptime(start_date, '%Y-%m-%d')
        self.scraped_urls = set()
        self.init_db()

    def init_db(self):
        try:
            conn = psycopg2.connect(**POSTGRES_SETTINGS)
            cur = conn.cursor()
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.target_table} (
                    url TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT,
                    publish_time TIMESTAMP NOT NULL,
                    author VARCHAR(255),
                    language VARCHAR(50) DEFAULT 'en',
                    section VARCHAR(100),
                    scraped_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            
            # 增量检查
            cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            max_date = cur.fetchone()[0]
            if max_date:
                self.cutoff_date = max_date
            
            cur.close()
            conn.close()
        except Exception as e:
            self.logger.error(f"DB init failed: {e}")

    def start_requests(self):
        # Ars Technica 分页示例：https://arstechnica.com/page/2/
        # 回溯至 2026-01-01 约需要翻 40-60 页
        for page in range(1, 80):
            url = self.start_urls[0] if page == 1 else f"{self.start_urls[0]}page/{page}/"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取所有文章链接 (li.article h2 a)
        articles = response.css('li.article h2 a::attr(href)').getall()
        # 针对 Featured 内容
        featured = response.css('header.article h2 a::attr(href)').getall()
        
        for link in set(articles + featured):
            if link and link.startswith('https') and ('/20' in link):
                if link in self.scraped_urls:
                    continue
                self.scraped_urls.add(link)
                yield scrapy.Request(link, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题解析
        title = response.css('h1::text').get() or response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'Unknown'

        # 正文解析：Ars Technica 主正文通常在 div.article-content 或 div[itemprop="articleBody"]
        content_html = response.css('.article-content').get() or response.css('div[itemprop="articleBody"]').get()
        
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            
            # 清理噪音
            for tag in soup(['script', 'style', 'aside', 'footer', 'div.ad-wrapper', 'div.gallery-popover-image']):
                tag.decompose()
            
            # 提取文本
            paragraphs = soup.find_all(['p', 'h2', 'h3'])
            content_parts = []
            for p in paragraphs:
                text = p.get_text().strip()
                if len(text) > 30 and 'Ars Technica' not in text:
                    content_parts.append(text)
            
            item['content'] = '\n\n'.join(content_parts)
        
        # 关键：获取准确的发布时间
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get()
        if not pub_time_str:
            pub_time_str = response.xpath('//time/@datetime').get()
            
        if pub_time_str:
            try:
                # 兼容 ISO 格式
                pub_dt = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                pub_time = pub_dt.replace(tzinfo=None)
            except:
                pub_time = datetime.now()
        else:
            pub_time = datetime.now()

        # 日期过滤
        if pub_time < self.cutoff_date:
            return

        item['publish_time'] = pub_time
        item['author'] = response.css('span[itemprop="name"]::text').get() or 'Ars Technica'
        item['language'] = 'en'
        item['section'] = response.css('nav.article-section a::text').get() or 'Technology'

        if item.get('content') and len(item['content']) > 150:
            yield item
