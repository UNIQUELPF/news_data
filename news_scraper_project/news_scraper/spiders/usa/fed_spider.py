import scrapy
import json
from datetime import datetime
from bs4 import BeautifulSoup
from news_scraper.utils import get_incremental_state

class USAFedSpider(scrapy.Spider):
    name = 'usa_fed'

    country_code = 'USA'

    country = '美国'
    allowed_domains = ['federalreserve.gov']
    # 直接请求官方公开的 JSON 索引
    start_urls = ['https://www.federalreserve.gov/json/ne-press.json']
    
    target_table = 'usa_fed_news'
    base_url = 'https://www.federalreserve.gov/'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
    }

    def __init__(self, start_date='2026-01-01', *args, **kwargs):
        super(USAFedSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime.strptime(start_date, '%Y-%m-%d')
        self.scraped_urls = set()
        self.init_db()

    def init_db(self):
        try:
            state = get_incremental_state(
                self.settings,
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=self.cutoff_date,
                full_scan=False,
            )
            self.cutoff_date = state["cutoff_date"]
            self.scraped_urls = state["scraped_urls"]
        except Exception as e:
            self.logger.error(f"DB init failed: {e}")

    def parse(self, response):
        try:
            data = json.loads(response.text)
            # Fed 官方 JSON 结构是一个新闻列表数组
            # 每个元素包含: {"d": "3/20/2026 4:30:00 PM", "t": "Title", "pt": "Section", "l": "/path/to.htm"}
            for record in data:
                relative_url = record.get('l')
                if not relative_url:
                    continue
                
                # 拼接完整 URL
                full_url = self.base_url + relative_url.lstrip('/')
                
                # 判定日期 "3/20/2026 4:30:00 PM" 或 "3/20/2026" 格式
                pub_time_str = record.get('d')
                try:
                    # 尝试常见的美式日期格式解析
                    pub_time = datetime.strptime(pub_time_str.split(' ')[0], '%m/%d/%Y')
                except:
                    pub_time = datetime.now()

                # 日期回溯过滤
                if pub_time < self.cutoff_date:
                    continue

                if full_url in self.scraped_urls:
                    continue
                self.scraped_urls.add(full_url)

                yield scrapy.Request(
                    full_url, 
                    callback=self.parse_article, 
                    meta={'title': record.get('t'), 'pub_time': pub_time, 'section': record.get('pt')}
                )
        except Exception as e:
            self.logger.error(f"Fed Index JSON parse failed: {e}")

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        item['title'] = response.meta['title']
        item['publish_time'] = response.meta['pub_time']
        item['section'] = response.meta['section']
        
        # 美联储官方内容主要位于 #article 或 .col-xs-12 内部
        content_parts = []
        body = response.css('#article').get() or response.css('div.col-xs-12').get()
        
        if body:
            soup = BeautifulSoup(body, 'html.parser')
            # 剔除噪音 (导航按钮、打印区域等)
            for tag in soup(['script', 'style', 'button', 'ul.nav', 'div.related-content']):
                tag.decompose()
            
            # 提取主要正文段落
            for p in soup.find_all(['p', 'h3', 'h4', 'div']):
                text = p.get_text().strip()
                # 过滤无意义的超短文字
                if len(text) > 40:
                    content_parts.append(text)
        
        item['content'] = '\n\n'.join(content_parts)
        item['author'] = 'Federal Reserve Board'
        item['language'] = 'en'

        if item.get('content') and len(item['content']) > 150:
            yield item
