from datetime import datetime

import psycopg2
import scrapy
from bs4 import BeautifulSoup
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state


class USAYFinanceSpider(scrapy.Spider):
    name = 'usa_yfinance'

    country_code = 'USA'

    country = '美国'
    allowed_domains = ['finance.yahoo.com']
    start_urls = ['https://finance.yahoo.com/topic/latest-news/']
    
    target_table = 'usa_yfinance_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
    }

    def __init__(self, start_date='2026-01-01', *args, **kwargs):
        super(USAYFinanceSpider, self).__init__(*args, **kwargs)
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
            
            cur.close()
            conn.close()
            state = get_incremental_state(
                getattr(self, "settings", None),
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=self.cutoff_date,
                full_scan=False,
            )
            self.cutoff_date = state["cutoff_date"]
            self.scraped_urls = state["scraped_urls"]
        except Exception as e:
            self.logger.error(f"DB init failed: {e}")

    def iter_start_requests(self):
        # 逐页请求直到触达 1 月 1 日
        # 雅虎翻页格式: /topic/latest-news/2/, /topic/latest-news/3/ ...
        for page in range(1, 150): # 150 页大约能涵盖 3 个月
            url = self.start_urls[0] if page == 1 else f"{self.start_urls[0]}{page}/"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def start_requests(self):
        yield from self.iter_start_requests()

    async def start(self):
        for request in self.iter_start_requests():
            yield request

    def parse_list(self, response):
        # 通过 CSS 选择器选取列表中的文章链接 (雅虎目前的列表 yf-119g04z 类)
        articles = response.css('a.subtle-link.fin-size-small::attr(href)').getall()
        # 备选选择器：雅虎的 href 通常包含 /news/ 或 /topic/
        if not articles:
            articles = response.xpath('//ul//li//a[contains(@href, "/news/")]/@href').getall()

        for link in articles:
            # 转换相对路径
            full_url = response.urljoin(link)
            
            # 过滤掉非文章链接
            if '/news/' not in full_url:
                continue
                
            if full_url in self.scraped_urls:
                continue
            
            self.scraped_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_article)

        # 检查最后一篇文章的日期
        # 如果当前页没有新文章，或者日期已经超过起始时间，会由 parse_article 里的逻辑停止请求
        # 但我们在列表页也做辅助判断

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 雅虎财经的标题样式 (yf-f60vsh 类)
        title = response.css('h1::text, h2::text').get() or response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'Unknown'

        # 正文提取：主要集中在 .caas-body 或 .body.yf-13q2nrc
        content_html = response.css('.caas-body').get() or response.css('div.body.yf-13q2nrc').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 剔除噪音 (雅虎内置的视频播放器占位符、图表助手等)
            for tag in soup(['script', 'style', 'button', 'svg', 'canvas']):
                tag.decompose()
            
            # 获取文本
            text = soup.get_text(separator='\n')
            lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) > 30]
            item['content'] = '\n\n'.join(lines)
        
        # 发布日期：从 meta 标签中提取最准确，雅虎通常有 ISO 格式
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get()
        if pub_time_str:
            try:
                pub_dt = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                pub_time = pub_dt.replace(tzinfo=None)
            except:
                pub_time = datetime.now()
        else:
            # 兜底：尝试解析页面文本显示的时间
            pub_time = datetime.now()

        # 日期过滤
        if pub_time < self.cutoff_date:
            return

        item['publish_time'] = pub_time
        item['author'] = response.css('span.caas-author-byline-collapse::text').get() or 'Yahoo Finance'
        item['language'] = 'en'
        item['section'] = 'Latest News'

        if item.get('content') and len(item['content']) > 100:
            yield item
