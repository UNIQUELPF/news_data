import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class MexicoExpansionSpider(BaseNewsSpider):
    name = 'mexico_expansion'
    allowed_domains = ['expansion.mx']
    start_urls = ['https://expansion.mx/economia']
    
    # 继承 BaseNewsSpider，自动初始化 mexico_expansion_news 表
    target_table = 'mexico_expansion_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # Expansion 分页格式为 ?page=1, ?page=2...
        # 深度回溯至 2026-01-01 约需 50 页
        for page in range(1, 51):
            url = f"{self.start_urls[0]}?page={page}"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取 CardGrid 中的文章链接
        articles = response.css('.CardGrid-items .Link::attr(href)').getall()
        # 兜底选择器
        if not articles:
            articles = response.css('a.Link::attr(href)').getall()

        for link in articles:
            full_url = response.urljoin(link)
            if '/202' in full_url: # 只抓取带年份的正式文章
                if full_url in self.scraped_urls:
                    continue
                self.scraped_urls.add(full_url)
                yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题提取 (Brightspot 典型标题)
        title = response.css('h1.ArticlePage-title::text').get() or response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'Unknown'

        # 正文提取：ArticlePage-body
        content_html = response.css('.ArticlePage-body').get() or response.css('.ArticlePage-content').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除相关推荐、广告以及亮眼的侧边栏
            for tag in soup(['script', 'style', '.RelatedContent', '.Ad', '.NewsletterSignup']):
                tag.decompose()
            
            # 清洗段落
            paragraphs = []
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if len(text) > 40:
                    paragraphs.append(text)
            
            item['content'] = "\n\n".join(paragraphs)
        
        # 精准发布日期从 meta 标签获取
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or \
                       response.xpath('//meta[@name="date"]/@content').get()
        
        if pub_time_str:
            try:
                # 兼容 ISO 格式
                pub_dt = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                pub_time = pub_dt.replace(tzinfo=None)
            except:
                pub_time = datetime.now()
        else:
            pub_time = datetime.now()

        # 日期过滤逻辑 (基类处理)
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = response.css('.ArticlePage-author::text').get() or 'Expansión'
        item['language'] = 'es' # 西班牙语
        item['section'] = 'Economía'

        if item.get('content') and len(item['content']) > 200:
            yield item
