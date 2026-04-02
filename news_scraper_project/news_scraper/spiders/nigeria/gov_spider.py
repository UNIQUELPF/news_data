import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class NigeriaGovSpider(BaseNewsSpider):
    name = 'ng_gov'
    allowed_domains = ['statehouse.gov.ng']
    start_urls = ['https://statehouse.gov.ng/category/press-releases/']
    
    # 继承 BaseNewsSpider，自动初始化 ng_gov_news 表
    target_table = 'ng_gov_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # State House 使用标准 WordPress 分页 /page/N/
        # 该站政务密集，回溯至 2026-01-01 约需 50-80 页
        for page in range(1, 81):
            url = self.start_urls[0] if page == 1 else f"{self.start_urls[0]}page/{page}/"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取状态府新闻稿链接
        articles = response.css('.news-detail a::attr(href)').getall() or \
                   response.css('.news-item a::attr(href)').getall()

        for link in articles:
            full_url = response.urljoin(link)
            if full_url in self.scraped_urls:
                continue
            self.scraped_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题提取 (官方通报标题通常由 H1 承载)
        title = response.css('h1::text').get() or response.css('.entry-title::text').get() or \
                response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'Official Statement'

        # 正文提取：定位 entry-content 或 main-content
        content_html = response.css('.post-content').get() or response.css('.entry-content').get() or \
                       response.css('article').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除冗余
            for tag in soup(['script', 'style', '.sharedaddy', '.jp-relatedposts']):
                tag.decompose()
            
            # 提取段落文本
            paragraphs = []
            for p in soup.find_all(['p', 'div']):
                # 过滤掉过于短小的段落
                text = p.get_text().strip()
                if len(text) > 40 and not text.startswith(('Follow us', 'Read also')):
                    paragraphs.append(text)
            
            # 使用列表去重并保持顺序
            seen = set()
            unique_paragraphs = [x for x in paragraphs if not (x in seen or seen.add(x))]
            item['content'] = "\n\n".join(unique_paragraphs)
        
        # 发布时间（尼日利亚总统府 GMT+1）
        pub_time_str = response.css('.news-info span::text').get() or \
                       response.css('.entry-date::text').get() or \
                       response.xpath('//meta[@property="article:published_time"]/@content').get()
        
        if pub_time_str:
            try:
                # 兼容 "March 21, 2026" 或 ISO 格式
                from dateutil import parser
                pub_dt = parser.parse(pub_time_str)
                pub_time = pub_dt.replace(tzinfo=None)
            except:
                pub_time = datetime.now()
        else:
            pub_time = datetime.now()

        # 日期过滤逻辑 (基类处理)
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = 'Presidential Villa, Abuja'
        item['language'] = 'en'
        item['section'] = 'Press Release'

        if item.get('content') and len(item['content']) > 200:
            yield item
